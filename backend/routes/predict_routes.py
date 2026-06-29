"""
routes/predict_routes.py
Prediction: single client (manual form), bulk CSV upload, history.
"""
from __future__ import annotations

import io

import pandas as pd
from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import jwt_required

from extensions import db
from models import Client, Prediction, MLModel, ExplicationSHAP
from security import current_company_id, current_user_id, admin_required
from services.client_service import ClientService
from services.prediction_service import PredictionService
from services.audit_service import log_action
from services.export_service import ExportService

predict_bp = Blueprint("predict", __name__)


# ── Single prediction (manual form) ──────────────────────────────────────────

@predict_bp.route("/single", methods=["POST"])
@jwt_required()
@admin_required
def predict_single():
    """
    Score a single client from manually entered form data.
    Creates or updates the client record, saves prediction, fires alerts.
    """
    cid  = current_company_id()
    uid  = current_user_id()
    data = request.get_json(force=True) or {}

    if not PredictionService.is_model_ready():
        return jsonify({"error": "Aucun modèle actif. Uploadez et entraînez un dataset d'abord."}), 503

    code_client = data.get("CODE_CLIENT") or data.get("code_client")
    if not code_client:
        return jsonify({"error": "CODE_CLIENT est requis"}), 400

    # Get/create client
    extra = {
        "nom":           data.get("nom"),
        "gouvernorat":   data.get("GOUVERNORAT") or data.get("gouvernorat"),
        "nature_client": data.get("NATURE_CLIENT") or data.get("nature_client"),
        "anciennete":    int(data.get("ANCIENNETE_CLIENT", data.get("anciennete", 0))),
    }
    client = ClientService.get_or_create(cid, str(code_client), extra)
    client.last_features = data   # store for future re-scoring

    # Run prediction
    try:
        result = PredictionService.predict(data)
    except Exception as e:
        return jsonify({"error": f"Erreur prédiction: {e}"}), 500

    # Persist prediction record
    active_model = MLModel.query.filter_by(company_id=cid, is_active=True).first()
    pred = Prediction(
        company_id=cid,
        client_id=client.id,
        model_id=active_model.id if active_model else None,
        predicted_by=uid,
        label=result["label"],
        risk_score=result["risk_score"],
        risk_level=result["risk_level"],
        probability=result["probability"],
        probability_risk=result["probability_risk"],
        threshold_used=result["threshold_used"],
        ai_summary=result["ai_summary"],
        shap_factors=result["top_factors"],
        input_data=data,
    )
    db.session.add(pred)

    # Persist SHAP explanations (rapport: ExplicationSHAP table)
    db.session.flush()   # get pred.id
    for factor in (result.get("top_factors") or [])[:10]:
        expl = ExplicationSHAP(
            prediction_id=pred.id,
            variable_importante=factor.get("feature"),
            impact=factor.get("shap_value"),
            description=f"Impact {'positif' if (factor.get('shap_value') or 0) > 0 else 'négatif'} "
                        f"sur la solvabilité (valeur={factor.get('feature_value', 0):.2f})",
        )
        db.session.add(expl)

    # Update client risk fields & score history
    ClientService.update_from_prediction(client, result)
    ClientService.log_score(client, result["risk_score"], result["risk_level"])

    # Update financials from input
    if "TOTAL_IMPAYE" in data:
        client.total_impaye  = float(data["TOTAL_IMPAYE"])
    if "credit_utilise" in data:
        client.credit_utilise = float(data["credit_utilise"])

    # Create alerts
    ClientService.check_and_create_alerts(client, result)

    db.session.commit()
    log_action(cid, uid, "PREDICT_SINGLE", "client", str(client.id))

    return jsonify({
        "prediction": result,
        "client":     client.to_dict(),
        "prediction_id": pred.id,
    })


# ── Bulk prediction (CSV/Excel upload) ────────────────────────────────────────

@predict_bp.route("/bulk", methods=["POST"])
@jwt_required()
@admin_required
def predict_bulk():
    """
    Upload a CSV/Excel file of clients, score all of them.
    Returns JSON results and optionally an Excel file.
    """
    cid = current_company_id()
    uid = current_user_id()

    if not PredictionService.is_model_ready():
        return jsonify({"error": "Aucun modèle actif"}), 503

    if "file" not in request.files:
        return jsonify({"error": "Fichier requis (champ 'file')"}), 400

    file = request.files["file"]
    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(file, sep=None, engine="python", encoding="utf-8-sig")
        else:
            df = pd.read_excel(file)
    except Exception as e:
        return jsonify({"error": f"Impossible de lire le fichier: {e}"}), 422

    records = df.to_dict(orient="records")
    raw_results = PredictionService.predict_batch(records)

    # Persist each result
    active_model = MLModel.query.filter_by(company_id=cid, is_active=True).first()
    enriched = []
    for raw, rec in zip(raw_results, records):
        if raw.get("error"):
            enriched.append(raw)
            continue
        code = str(rec.get("CODE_CLIENT", ""))
        client = ClientService.get_or_create(cid, code) if code else None
        if client:
            ClientService.update_from_prediction(client, raw)
            ClientService.log_score(client, raw["risk_score"], raw["risk_level"])
            pred = Prediction(
                company_id=cid, client_id=client.id,
                model_id=active_model.id if active_model else None,
                predicted_by=uid, label=raw["label"],
                risk_score=raw["risk_score"], risk_level=raw["risk_level"],
                probability=raw["probability"], probability_risk=raw["probability_risk"],
                threshold_used=raw["threshold_used"], ai_summary=raw["ai_summary"],
                shap_factors=raw["top_factors"], input_data=rec,
            )
            db.session.add(pred)
            ClientService.check_and_create_alerts(client, raw)
        enriched.append(raw)

    db.session.commit()
    log_action(cid, uid, "PREDICT_BULK", "dataset", None, {"count": len(enriched)})

    # Optional Excel export
    export_excel = request.args.get("export", "false").lower() == "true"
    if export_excel:
        xlsx = ExportService.bulk_results_to_excel(enriched)
        return send_file(
            io.BytesIO(xlsx),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="resultats_scoring.xlsx",
        )

    return jsonify({
        "results": enriched,
        "total":   len(enriched),
        "solvable":    sum(1 for r in enriched if r.get("label") == "SOLVABLE"),
        "non_solvable": sum(1 for r in enriched if r.get("label") == "NON-SOLVABLE"),
        "errors":       sum(1 for r in enriched if r.get("error")),
    })


# ── Prediction history ────────────────────────────────────────────────────────

@predict_bp.route("/history", methods=["GET"])
@jwt_required()
def prediction_history():
    cid      = current_company_id()
    page     = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 50)), 200)
    client_id = request.args.get("client_id")

    q = Prediction.query.filter_by(company_id=cid)
    if client_id:
        q = q.filter_by(client_id=int(client_id))

    pag = q.order_by(Prediction.predicted_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        "predictions": [p.to_dict() for p in pag.items],
        "total": pag.total, "pages": pag.pages, "page": page,
    })


@predict_bp.route("/history/<int:pred_id>", methods=["GET"])
@jwt_required()
def get_prediction(pred_id: int):
    pred = Prediction.query.filter_by(
        id=pred_id, company_id=current_company_id()
    ).first_or_404()
    return jsonify({"prediction": pred.to_dict()})


# ── Model readiness check ─────────────────────────────────────────────────────

@predict_bp.route("/ready", methods=["GET"])
@jwt_required()
def model_ready():
    return jsonify({
        "ready":      PredictionService.is_model_ready(),
        "model_type": PredictionService.get_model_type(),
    })

@predict_bp.route("/solvabilite", methods=["GET"])
@jwt_required()
def consulter_resultats_solvabilite():
    """Cas d'utilisation: Consulter les résultats de solvabilité."""
    cid = current_company_id()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 50)), 200)
    q = Client.query.filter_by(company_id=cid)
    search = (request.args.get("q") or "").strip()
    if search:
        like = f"%{search}%"
        q = q.filter((Client.code_client.ilike(like)) | (Client.nom.ilike(like)))
    pag = q.order_by(Client.score_actuel.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "clients": [c.to_dict() for c in pag.items],
        "total": pag.total,
        "pages": pag.pages,
        "page": page,
    })

"""
routes/client_routes.py
Client management: CRUD, 360 profile, alerts, relances, credit limit, PDF, export.
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import jwt_required
import io

from extensions import db
from models import Client, Alert, Relance
from security import current_user_id, current_company_id, manager_or_admin, admin_required
from services.client_service import ClientService
from services.audit_service import log_action
from services.export_service import ExportService
from services.pdf_generator import generate_client_report

client_bp = Blueprint("clients", __name__)


# ── List & search ─────────────────────────────────────────────────────────────

@client_bp.route("", methods=["GET"])
@jwt_required()
def list_clients():
    cid = current_company_id()
    page     = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)

    paginator = ClientService.search(
        company_id=cid,
        q=request.args.get("q", ""),
        risk_level=request.args.get("risk_level", ""),
        statut=request.args.get("statut", ""),
        gouvernorat=request.args.get("gouvernorat", ""),
        nature_client=request.args.get("nature_client", ""),
        score_min=int(request.args.get("score_min", 0)),
        score_max=int(request.args.get("score_max", 100)),
        page=page,
        per_page=per_page,
        sort_by=request.args.get("sort_by", "score_actuel"),
        sort_dir=request.args.get("sort_dir", "desc"),
    )
    return jsonify({
        "clients": [c.to_dict() for c in paginator.items],
        "total":   paginator.total,
        "pages":   paginator.pages,
        "page":    page,
        "per_page": per_page,
    })


# ── Create client ─────────────────────────────────────────────────────────────

@client_bp.route("", methods=["POST"])
@jwt_required()
@admin_required
def create_client():
    cid  = current_company_id()
    data = request.get_json(force=True) or {}
    if not data.get("code_client"):
        return jsonify({"error": "code_client est requis"}), 400

    extra = {k: data[k] for k in [
        "nom", "email", "telephone", "gouvernorat",
        "nature_client", "statut", "plafond_credit", "anciennete",
    ] if k in data}

    client = ClientService.get_or_create(cid, data["code_client"], extra)
    db.session.commit()
    log_action(cid, current_user_id(), "CREATE_CLIENT", "client", str(client.id))
    return jsonify({"client": client.to_dict()}), 201


@client_bp.route("/top-risk", methods=["GET"])
@jwt_required()
def top_risk_clients():
    """Liste des meilleurs clients à risque, affichée dans la page Clients."""
    cid = current_company_id()
    limit = min(int(request.args.get("limit", 20)), 100)
    clients = ClientService.top_risk_clients(cid, limit)
    return jsonify({"clients": clients, "total": len(clients)})


# ── Get single client ─────────────────────────────────────────────────────────

@client_bp.route("/<int:client_id>", methods=["GET"])
@jwt_required()
def get_client(client_id: int):
    client = _get_or_404(client_id)
    return jsonify({"client": client.to_dict()})


# ── Update client ─────────────────────────────────────────────────────────────

@client_bp.route("/<int:client_id>", methods=["PUT"])
@jwt_required()
@admin_required
def update_client(client_id: int):
    client = _get_or_404(client_id)
    data   = request.get_json(force=True) or {}
    editable = ["nom", "email", "telephone", "gouvernorat", "nature_client", "statut", "anciennete"]
    for field in editable:
        if field in data:
            setattr(client, field, data[field])
    db.session.commit()
    log_action(current_company_id(), current_user_id(), "UPDATE_CLIENT", "client", str(client_id))
    return jsonify({"client": client.to_dict()})


# ── Delete client ─────────────────────────────────────────────────────────────

@client_bp.route("/<int:client_id>", methods=["DELETE"])
@jwt_required()
@admin_required
def delete_client(client_id: int):
    client = _get_or_404(client_id)
    db.session.delete(client)
    db.session.commit()
    log_action(current_company_id(), current_user_id(), "DELETE_CLIENT", "client", str(client_id))
    return jsonify({"message": "Client supprimé"})


# ── 360 Profile ───────────────────────────────────────────────────────────────

@client_bp.route("/<int:client_id>/profile", methods=["GET"])
@jwt_required()
def client_profile(client_id: int):
    client = _get_or_404(client_id)   # ownership check
    log_action(current_company_id(), current_user_id(), "CONSULT_CLIENT_PROFILE", "client", str(client_id), {
        "code_client": client.code_client,
        "nom": client.nom,
    })
    db.session.commit()
    profile = ClientService.get_profile(client_id)
    return jsonify(profile)


# ── Credit limit ──────────────────────────────────────────────────────────────

@client_bp.route("/<int:client_id>/credit-limit", methods=["PUT"])
@jwt_required()
@admin_required
def set_credit_limit(client_id: int):
    client = _get_or_404(client_id)
    data   = request.get_json(force=True) or {}
    plafond = data.get("plafond_credit")
    if plafond is None or float(plafond) < 0:
        return jsonify({"error": "plafond_credit invalide"}), 400
    cl = ClientService.set_credit_limit(client, float(plafond), current_user_id())
    db.session.commit()
    log_action(current_company_id(), current_user_id(), "SET_CREDIT_LIMIT",
               "client", str(client_id), {"plafond": plafond})
    return jsonify({"credit_limit": cl.to_dict()})


# ── Alerts ────────────────────────────────────────────────────────────────────

@client_bp.route("/<int:client_id>/alerts", methods=["GET"])
@jwt_required()
def get_alerts(client_id: int):
    _get_or_404(client_id)
    include_resolved = request.args.get("include_resolved", "false").lower() == "true"
    q = Alert.query.filter_by(client_id=client_id)
    if not include_resolved:
        q = q.filter(Alert.resolved_at.is_(None))
    alerts = q.order_by(Alert.created_at.desc()).all()
    return jsonify({"alerts": [a.to_dict() for a in alerts]})


@client_bp.route("/alerts/<int:alert_id>/resolve", methods=["POST"])
@jwt_required()
@admin_required
def resolve_alert(alert_id: int):
    alert = Alert.query.filter_by(
        id=alert_id, company_id=current_company_id()
    ).first_or_404()
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by = current_user_id()
    db.session.commit()
    return jsonify({"alert": alert.to_dict()})


# ── Relances ──────────────────────────────────────────────────────────────────

@client_bp.route("/<int:client_id>/relances", methods=["GET"])
@jwt_required()
def get_relances(client_id: int):
    _get_or_404(client_id)
    relances = (
        Relance.query.filter_by(client_id=client_id)
        .order_by(Relance.created_at.desc())
        .limit(50).all()
    )
    return jsonify({"relances": [r.to_dict() for r in relances]})


@client_bp.route("/<int:client_id>/relances", methods=["POST"])
@jwt_required()
@admin_required
def create_relance(client_id: int):
    client = _get_or_404(client_id)
    data   = request.get_json(force=True) or {}
    required = ["type", "message"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Champs requis: {missing}"}), 400

    relance = ClientService.create_relance(
        client=client,
        relance_type=data["type"],
        message=data["message"],
        montant_vise=float(data.get("montant_vise", 0)),
        user_id=current_user_id(),
    )
    db.session.commit()
    log_action(current_company_id(), current_user_id(), "CREATE_RELANCE",
               "client", str(client_id))
    return jsonify({"relance": relance.to_dict()}), 201


@client_bp.route("/relances/<int:relance_id>", methods=["PUT"])
@jwt_required()
@admin_required
def update_relance(relance_id: int):
    relance = Relance.query.filter_by(
        id=relance_id, company_id=current_company_id()
    ).first_or_404()
    data = request.get_json(force=True) or {}
    if "statut" in data:
        relance.statut = data["statut"]
    db.session.commit()
    return jsonify({"relance": relance.to_dict()})


# ── PDF Export ────────────────────────────────────────────────────────────────

@client_bp.route("/<int:client_id>/report/pdf", methods=["GET"])
@jwt_required()
def download_pdf(client_id: int):
    _get_or_404(client_id)
    profile = ClientService.get_profile(client_id)
    pdf_bytes = generate_client_report(profile)
    code = profile["client"].get("code_client", str(client_id))
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"rapport_credit_{code}.pdf",
    )


# ── Excel / CSV export ────────────────────────────────────────────────────────

@client_bp.route("/export/excel", methods=["GET"])
@jwt_required()
@admin_required
def export_excel():
    cid = current_company_id()
    clients = Client.query.filter_by(company_id=cid).all()
    data = [c.to_dict() for c in clients]
    xlsx_bytes = ExportService.clients_to_excel(data)
    return send_file(
        io.BytesIO(xlsx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="clients_solvai.xlsx",
    )


@client_bp.route("/export/csv", methods=["GET"])
@jwt_required()
@admin_required
def export_csv():
    cid = current_company_id()
    clients = Client.query.filter_by(company_id=cid).all()
    data = [c.to_dict() for c in clients]
    csv_str = ExportService.clients_to_csv(data)
    return send_file(
        io.BytesIO(csv_str.encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="clients_solvai.csv",
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_404(client_id: int) -> Client:
    return Client.query.filter_by(
        id=client_id, company_id=current_company_id()
    ).first_or_404()

# ── UML conception compatibility endpoints ───────────────────────────────────
# These endpoints expose the exact actions shown in the conception diagrams:
# consulter score, consulter explications SHAP, analyser historique paiement,
# analyser comportement commercial.

@client_bp.route("/<int:client_id>/score", methods=["GET"])
@jwt_required()
def consulter_score_risque(client_id: int):
    client = _get_or_404(client_id)
    return jsonify({
        "client_id": client.id,
        "code_client": client.code_client,
        "score_risque": client.score_actuel,
        "niveau_solvabilite": client.risk_level,
        "derniere_analyse": client.derniere_analyse.isoformat() if client.derniere_analyse else None,
    })


@client_bp.route("/<int:client_id>/explications-shap", methods=["GET"])
@jwt_required()
def consulter_explications_shap(client_id: int):
    from models import Prediction, ExplicationSHAP
    client = _get_or_404(client_id)
    pred = (Prediction.query.filter_by(client_id=client.id, company_id=current_company_id())
            .order_by(Prediction.predicted_at.desc()).first())
    if not pred:
        return jsonify({"explications": [], "message": "Aucune prédiction disponible"})
    exps = ExplicationSHAP.query.filter_by(prediction_id=pred.id).all()
    return jsonify({
        "prediction": pred.to_dict(),
        "explications": [e.to_dict() for e in exps],
        "shap_factors": pred.shap_factors or [],
    })


@client_bp.route("/<int:client_id>/historique-paiement", methods=["GET"])
@jwt_required()
def analyser_historique_paiement(client_id: int):
    from models import PaymentHistory, Invoice
    client = _get_or_404(client_id)
    payments = (PaymentHistory.query.filter_by(client_id=client.id)
                .order_by(PaymentHistory.date.desc()).limit(100).all())
    invoices = (Invoice.query.filter_by(client_id=client.id)
                .order_by(Invoice.date_facture.desc()).limit(100).all())
    total_paiements = sum(float(p.montant or 0) for p in payments)
    total_factures = sum(float(i.montant_facture or 0) for i in invoices)
    nb_retards = sum(1 for p in payments if (p.delai or 0) > 0)
    retard_moyen = round(sum(float(p.delai or 0) for p in payments) / max(1, len(payments)), 2)
    return jsonify({
        "client": client.to_dict(),
        "resume": {
            "total_paiements": total_paiements,
            "total_factures": total_factures,
            "nb_retards": nb_retards,
            "retard_moyen": retard_moyen,
        },
        "paiements": [p.to_dict() for p in payments],
        "factures": [i.to_dict() for i in invoices],
    })


@client_bp.route("/<int:client_id>/comportement-commercial", methods=["GET"])
@jwt_required()
def analyser_comportement_commercial(client_id: int):
    client = _get_or_404(client_id)
    features = client.last_features or {}
    return jsonify({
        "client": client.to_dict(),
        "comportement": {
            "total_achats": features.get("TOTAL_MONTANT_TTC", client.credit_utilise or 0),
            "total_paiements": features.get("TOTAL_MONTANT_REG", 0),
            "nb_factures": features.get("NB_FACTURES", 0),
            "nb_reglements": features.get("NB_REGLEMENTS", 0),
            "frequence_achat": features.get("FREQUENCE_ACHAT", 0),
            "anciennete_client": features.get("ANCIENNETE_CLIENT", client.anciennete or 0),
            "jours_depuis_dernier_achat": features.get("JOURS_DEPUIS_DERNIER_ACHAT", 0),
            "ratio_paiement": features.get("RATIO_PAIEMENT", 0),
            "part_ca_client": features.get("PART_CA_CLIENT", 0),
        }
    })

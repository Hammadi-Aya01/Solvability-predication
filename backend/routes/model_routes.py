"""
routes/model_routes.py
ML model versioning: list, activate, rollback, performance comparison, drift.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from extensions import db
from models import MLModel
from security import current_company_id, current_user_id, manager_or_admin, admin_required
from services.audit_service import log_action
from services.prediction_service import PredictionService

model_bp = Blueprint("models", __name__)


# ── List models ───────────────────────────────────────────────────────────────

@model_bp.route("", methods=["GET"])
@jwt_required()
@admin_required
def list_models():
    cid  = current_company_id()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 50)
    pag = (
        MLModel.query.filter_by(company_id=cid)
        .order_by(MLModel.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return jsonify({
        "models": [m.to_dict() for m in pag.items],
        "total": pag.total, "pages": pag.pages, "page": page,
    })


@model_bp.route("/active", methods=["GET"])
@jwt_required()
def get_active_model():
    cid = current_company_id()
    model = MLModel.query.filter_by(company_id=cid, is_active=True).first()
    if not model:
        return jsonify({"model": None, "message": "Aucun modèle actif"}), 200
    return jsonify({"model": model.to_dict()})


@model_bp.route("/<int:model_id>", methods=["GET"])
@jwt_required()
@admin_required
def get_model(model_id: int):
    model = _get_or_404(model_id)
    return jsonify({"model": model.to_dict()})


# ── Activate / rollback ───────────────────────────────────────────────────────

@model_bp.route("/<int:model_id>/activate", methods=["POST"])
@jwt_required()
@admin_required
def activate_model(model_id: int):
    """
    Activate a specific model version.
    Deactivates the previously active model, loads the new one into memory.
    """
    cid   = current_company_id()
    model = _get_or_404(model_id)

    if not model.artifact_paths:
        return jsonify({"error": "Artéfacts du modèle introuvables"}), 422

    # Deactivate all other models for this company
    MLModel.query.filter_by(company_id=cid, is_active=True).update({"is_active": False})
    model.is_active = True
    db.session.commit()

    # Load into predictor
    try:
        PredictionService.load_active_model(model)
        message = f"Modèle {model.model_name} v{model.version} activé avec succès"
    except Exception as e:
        message = f"Modèle activé en DB mais erreur de chargement mémoire: {e}"

    log_action(cid, current_user_id(), "ACTIVATE_MODEL", "ml_model", str(model_id),
               {"model_name": model.model_name, "version": model.version})

    return jsonify({"message": message, "model": model.to_dict()})


@model_bp.route("/<int:model_id>", methods=["DELETE"])
@jwt_required()
@admin_required
def delete_model(model_id: int):
    model = _get_or_404(model_id)
    if model.is_active:
        return jsonify({"error": "Impossible de supprimer le modèle actif"}), 409
    db.session.delete(model)
    db.session.commit()
    log_action(current_company_id(), current_user_id(), "DELETE_MODEL", "ml_model", str(model_id))
    return jsonify({"message": "Modèle supprimé"})


# ── Performance comparison ────────────────────────────────────────────────────

@model_bp.route("/compare", methods=["GET"])
@jwt_required()
@admin_required
def compare_models():
    """Compare latest N model versions by their metrics."""
    cid   = current_company_id()
    limit = int(request.args.get("limit", 5))
    models = (
        MLModel.query.filter_by(company_id=cid)
        .order_by(MLModel.created_at.desc())
        .limit(limit).all()
    )
    rows = []
    for m in models:
        rows.append({
            "id": m.id, "model_name": m.model_name, "version": m.version,
            "is_active": m.is_active,
            "roc_auc":   m.roc_auc,   "f1_score":  m.f1_score,
            "accuracy":  m.accuracy,  "precision": m.precision,
            "recall":    m.recall,    "threshold": m.threshold,
            "created_at": m.created_at.isoformat(),
        })
    return jsonify({"comparison": rows})


# ── Feature importances ───────────────────────────────────────────────────────

@model_bp.route("/<int:model_id>/feature-importances", methods=["GET"])
@jwt_required()
@admin_required
def feature_importances(model_id: int):
    model = _get_or_404(model_id)
    fi = model.feature_importances or {}
    # Sort by importance desc
    sorted_fi = sorted(fi.items(), key=lambda x: x[1], reverse=True)
    return jsonify({
        "model_id": model_id,
        "model_name": model.model_name,
        "feature_importances": [{"feature": k, "importance": v} for k, v in sorted_fi],
    })


# ── Drift report ──────────────────────────────────────────────────────────────

@model_bp.route("/<int:model_id>/drift", methods=["POST"])
@jwt_required()
@admin_required
def check_drift(model_id: int):
    """
    Compute PSI drift between a new dataset and the model's training data.
    Expects JSON: { "dataset_id": <int> }
    """
    model = _get_or_404(model_id)
    data  = request.get_json(force=True) or {}
    dataset_id = data.get("dataset_id")
    if not dataset_id:
        return jsonify({"error": "dataset_id requis"}), 400

    from models import Dataset
    import pandas as pd

    dataset = Dataset.query.filter_by(
        id=dataset_id, company_id=current_company_id()
    ).first_or_404()

    try:
        resolved_path = dataset.resolved_file_path
        if resolved_path.endswith(".csv"):
            df = pd.read_csv(resolved_path, sep=None, engine="python", encoding="utf-8-sig")
        else:
            df = pd.read_excel(resolved_path)
    except Exception as e:
        return jsonify({"error": f"Impossible de lire le dataset: {e}"}), 422

    feature_names = model.feature_importances.keys() if model.feature_importances else []
    if not feature_names:
        return jsonify({"error": "Pas d'importances de features sur ce modèle"}), 422

    from services.prediction_service import PredictionService
    drift = PredictionService.check_drift(df, list(feature_names))
    return jsonify({"drift_report": drift, "model_id": model_id})


# ── Model ready status ────────────────────────────────────────────────────────

@model_bp.route("/status", methods=["GET"])
@jwt_required()
def model_status():
    return jsonify({
        "ready":     PredictionService.is_model_ready(),
        "model_type": PredictionService.get_model_type(),
    })


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_or_404(model_id: int) -> MLModel:
    return MLModel.query.filter_by(
        id=model_id, company_id=current_company_id()
    ).first_or_404()

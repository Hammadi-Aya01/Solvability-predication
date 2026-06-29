"""
routes/dashboard_routes.py
Dashboard analytics endpoints: KPIs, risk distribution, score evolution, alerts, etc.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from security import current_company_id, admin_required
from services.analytics_service import AnalyticsService

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/kpis", methods=["GET"])
@jwt_required()
def kpis():
    """Main dashboard KPIs."""
    cid = current_company_id()
    data = AnalyticsService.dashboard_kpis(cid)
    return jsonify(data)


@dashboard_bp.route("/score-evolution", methods=["GET"])
@jwt_required()
def score_evolution():
    """Average score evolution over the last N days."""
    cid  = current_company_id()
    days = int(request.args.get("days", 30))
    return jsonify({"data": AnalyticsService.score_evolution(cid, days)})


@dashboard_bp.route("/top-risk", methods=["GET"])
@jwt_required()
def top_risk():
    """Top N high-risk clients."""
    cid   = current_company_id()
    limit = int(request.args.get("limit", 10))
    return jsonify({"clients": AnalyticsService.top_risk_clients(cid, limit)})


@dashboard_bp.route("/payment-modes", methods=["GET"])
@jwt_required()
def payment_modes():
    """Payment mode statistics."""
    cid = current_company_id()
    return jsonify({"data": AnalyticsService.payment_mode_stats(cid)})


@dashboard_bp.route("/prediction-history", methods=["GET"])
@jwt_required()
def prediction_history():
    """Daily prediction volume over last N days."""
    cid  = current_company_id()
    days = int(request.args.get("days", 30))
    return jsonify({"data": AnalyticsService.prediction_history(cid, days)})


@dashboard_bp.route("/gouvernorat-stats", methods=["GET"])
@jwt_required()
def gouvernorat_stats():
    """Risk stats by gouvernorat."""
    cid = current_company_id()
    return jsonify({"data": AnalyticsService.gouvernorat_stats(cid)})


@dashboard_bp.route("/audit", methods=["GET"])
@jwt_required()
@admin_required
def audit_log():
    """Recent audit log entries."""
    cid  = current_company_id()
    days = int(request.args.get("days", 7))
    return jsonify({"data": AnalyticsService.audit_summary(cid, days)})


@dashboard_bp.route("/alerts/summary", methods=["GET"])
@jwt_required()
def alerts_summary():
    """Count of unresolved alerts by severity."""
    from models import Alert
    from extensions import db
    from sqlalchemy import func
    cid = current_company_id()
    rows = (
        db.session.query(Alert.severity, func.count(Alert.id))
        .filter_by(company_id=cid)
        .filter(Alert.resolved_at.is_(None))
        .group_by(Alert.severity)
        .all()
    )
    return jsonify({"data": {sev: cnt for sev, cnt in rows}})


@dashboard_bp.route("/overview", methods=["GET"])
@jwt_required()
def full_overview():
    """
    Combined endpoint — returns all dashboard data in one request
    to minimise frontend round trips.
    """
    cid  = current_company_id()
    days = int(request.args.get("days", 30))

    return jsonify({
        "kpis":             AnalyticsService.dashboard_kpis(cid),
        "score_evolution":  AnalyticsService.score_evolution(cid, days),
        "payment_modes":    AnalyticsService.payment_mode_stats(cid),
        "pred_history":     AnalyticsService.prediction_history(cid, days),
        "gouvernorat":      AnalyticsService.gouvernorat_stats(cid),
    })

@dashboard_bp.route("/historique-systeme", methods=["GET"])
@jwt_required()
@admin_required
def historique_systeme():
    """Cas d'utilisation: Consulter l'historique système."""
    cid = current_company_id()
    days = int(request.args.get("days", 30))
    return jsonify({"data": AnalyticsService.audit_summary(cid, days)})

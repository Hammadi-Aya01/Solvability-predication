"""
services/analytics_service.py
Dashboard analytics, KPIs, portfolio statistics.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from sqlalchemy import func

from extensions import db, cache
from models import (
    Client, Prediction, ScoreHistory, Alert,
    Invoice, PaymentHistory, Relance, AuditLog, User,
)


class AnalyticsService:

    @staticmethod
    @cache.memoize(timeout=120)
    def dashboard_kpis(company_id: int) -> dict:
        total_clients = Client.query.filter_by(company_id=company_id).count()
        actifs   = Client.query.filter_by(company_id=company_id, statut="ACTIF").count()
        inactifs = total_clients - actifs

        risk_dist = (
            db.session.query(Client.risk_level, func.count(Client.id))
            .filter_by(company_id=company_id)
            .group_by(Client.risk_level).all()
        )
        risk_map = {r: int(c) for r, c in risk_dist}

        total_impaye = (
            db.session.query(func.sum(Client.total_impaye))
            .filter_by(company_id=company_id).scalar() or 0.0
        )
        total_credit_utilise = (
            db.session.query(func.sum(Client.credit_utilise))
            .filter_by(company_id=company_id).scalar() or 0.0
        )

        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0)
        preds_month = (
            Prediction.query.filter(
                Prediction.company_id == company_id,
                Prediction.predicted_at >= month_start,
            ).count()
        )

        active_alerts = (
            Alert.query.filter_by(company_id=company_id)
            .filter(Alert.resolved_at.is_(None)).count()
        )
        critical_alerts = (
            Alert.query.filter_by(company_id=company_id, severity="CRITICAL")
            .filter(Alert.resolved_at.is_(None)).count()
        )

        avg_score = (
            db.session.query(func.avg(Client.score_actuel))
            .filter_by(company_id=company_id).scalar() or 0.0
        )

        relances_pending = (
            Relance.query.filter_by(company_id=company_id, statut="PLANIFIEE").count()
        )

        return {
            "clients": {
                "total": total_clients, "actifs": actifs,
                "inactifs": inactifs, "avg_score": round(float(avg_score), 1),
            },
            "risk_distribution": {
                "FAIBLE":  risk_map.get("FAIBLE", 0),
                "MOYEN":   risk_map.get("MOYEN", 0),
                "ÉLEVÉ":   risk_map.get("ÉLEVÉ", 0),
                "INCONNU": risk_map.get("INCONNU", 0),
            },
            "financials": {
                "total_impaye":         round(float(total_impaye), 2),
                "total_credit_utilise": round(float(total_credit_utilise), 2),
            },
            "activity": {
                "predictions_this_month": preds_month,
                "active_alerts":          active_alerts,
                "critical_alerts":        critical_alerts,
                "relances_pending":       relances_pending,
            },
        }

    @staticmethod
    def score_evolution(company_id: int, days: int = 30) -> list[dict]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            db.session.query(
                func.date(ScoreHistory.predicted_at).label("day"),
                func.avg(ScoreHistory.risk_score).label("avg_score"),
                func.count(ScoreHistory.id).label("nb"),
            )
            .filter(ScoreHistory.company_id == company_id, ScoreHistory.predicted_at >= since)
            .group_by(func.date(ScoreHistory.predicted_at))
            .order_by(func.date(ScoreHistory.predicted_at))
            .all()
        )
        return [{"day": str(r.day), "avg_score": round(float(r.avg_score), 1), "nb": r.nb}
                for r in rows]

    @staticmethod
    def top_risk_clients(company_id: int, limit: int = 10) -> list[dict]:
        clients = (
            Client.query.filter_by(company_id=company_id)
            .filter(Client.risk_level == "ÉLEVÉ")
            .order_by(Client.score_actuel.desc()).limit(limit).all()
        )
        return [c.to_dict() for c in clients]

    @staticmethod
    def payment_mode_stats(company_id: int) -> list[dict]:
        rows = (
            db.session.query(
                PaymentHistory.mode,
                func.count(PaymentHistory.id).label("nb"),
                func.sum(PaymentHistory.montant).label("total"),
                func.avg(PaymentHistory.delai).label("avg_delai"),
            )
            .filter_by(company_id=company_id)
            .group_by(PaymentHistory.mode)
            .order_by(func.count(PaymentHistory.id).desc())
            .all()
        )
        return [{
            "mode": r.mode or "INCONNU", "nb": r.nb,
            "total": round(float(r.total or 0), 2),
            "avg_delai": round(float(r.avg_delai or 0), 1),
        } for r in rows]

    @staticmethod
    def prediction_history(company_id: int, days: int = 30) -> list[dict]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            db.session.query(
                func.date(Prediction.predicted_at).label("day"),
                Prediction.label,
                func.count(Prediction.id).label("nb"),
            )
            .filter(Prediction.company_id == company_id, Prediction.predicted_at >= since)
            .group_by(func.date(Prediction.predicted_at), Prediction.label)
            .order_by(func.date(Prediction.predicted_at))
            .all()
        )
        grouped: dict[str, dict] = {}
        for r in rows:
            d = str(r.day)
            if d not in grouped:
                grouped[d] = {"day": d, "SOLVABLE": 0, "NON-SOLVABLE": 0, "total": 0}
            grouped[d][r.label] = r.nb
            grouped[d]["total"] += r.nb
        return list(grouped.values())

    @staticmethod
    def gouvernorat_stats(company_id: int) -> list[dict]:
        rows = (
            db.session.query(
                Client.gouvernorat,
                func.count(Client.id).label("nb_clients"),
                func.avg(Client.score_actuel).label("avg_score"),
                func.sum(Client.total_impaye).label("total_impaye"),
            )
            .filter_by(company_id=company_id)
            .group_by(Client.gouvernorat)
            .order_by(func.avg(Client.score_actuel).desc())
            .all()
        )
        return [{
            "gouvernorat":  r.gouvernorat or "INCONNU",
            "nb_clients":   r.nb_clients,
            "avg_score":    round(float(r.avg_score or 0), 1),
            "total_impaye": round(float(r.total_impaye or 0), 2),
        } for r in rows]

    @staticmethod
    def audit_summary(company_id: int, days: int = 7) -> list[dict]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            AuditLog.query.filter_by(company_id=company_id)
            .filter(AuditLog.created_at >= since)
            .order_by(AuditLog.created_at.desc()).limit(100).all()
        )
        users = {u.id: u for u in User.query.filter_by(company_id=company_id).all()}
        result = []
        for row in rows:
            item = row.to_dict()
            user = users.get(row.user_id)
            item["actor"] = user.full_name() if user else "Système"
            item["actor_role"] = user.role if user else "SYSTEM"
            item["description"] = _audit_description(row, user)
            result.append(item)
        return result


def _audit_description(row: AuditLog, user: User | None) -> str:
    actor = user.full_name() if user else "Le système"
    action = row.action or "ACTION"
    detail = row.detail or {}
    if action == "LOGIN":
        return f"{actor} s'est authentifié."
    if action == "LOGOUT":
        return f"{actor} s'est déconnecté."
    if action == "CREATE_USER":
        return f"{actor} a ajouté un utilisateur."
    if action == "UPDATE_USER":
        return f"{actor} a modifié un utilisateur."
    if action == "DELETE_USER":
        return f"{actor} a supprimé un utilisateur."
    if action == "UPLOAD_DATASET":
        return f"{actor} a importé un dataset."
    if action in ("TRAIN_MODEL", "MODEL_TRAINED"):
        return f"{actor} a lancé ou validé un entraînement de modèle."
    if action == "CONSULT_CLIENT_PROFILE":
        code = detail.get("code_client") or row.resource_id
        return f"{actor} a consulté le profil du client {code}."
    if action == "CREATE_CLIENT":
        return f"{actor} a ajouté un client."
    if action == "UPDATE_CLIENT":
        return f"{actor} a modifié un client."
    if action == "DELETE_CLIENT":
        return f"{actor} a supprimé un client."
    return f"{actor} a effectué l'action {action}."

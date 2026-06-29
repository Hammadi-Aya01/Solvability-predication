"""
services/client_service.py
Re-exports ClientService defined in services/ml_client_service.py
for cleaner imports in routes.
"""
# The actual implementation lives in the txt source as app/services/client_service.py.
# Here we adapt imports to match this project's flat structure.

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import or_

from extensions import db
from models import (
    Client, ScoreHistory, PaymentHistory, Invoice,
    Alert, Relance, CreditLimit, AuditLog, Prediction,
)


class ClientService:

    # ── CRUD ──────────────────────────────────────────────────────────────

    @staticmethod
    def get_or_create(company_id: int, code_client: str, extra: dict | None = None) -> Client:
        client = Client.query.filter_by(
            company_id=company_id, code_client=str(code_client)
        ).first()
        if client is None:
            client = Client(
                company_id=company_id,
                code_client=str(code_client),
                **(extra or {}),
            )
            db.session.add(client)
            db.session.flush()
        elif extra:
            for k, v in extra.items():
                if hasattr(client, k) and v is not None:
                    setattr(client, k, v)
        return client

    @staticmethod
    def update_from_prediction(client: Client, result: dict) -> None:
        client.score_actuel     = result["risk_score"]
        client.risk_level       = result["risk_level"]
        client.derniere_analyse = datetime.now(timezone.utc)
        db.session.flush()

    @staticmethod
    def update_statut(company_id: int, inactivity_days: int = 180) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=inactivity_days)
        clients = Client.query.filter_by(company_id=company_id).all()
        updated = 0
        for c in clients:
            last_inv = (
                Invoice.query.filter_by(client_id=c.id)
                .order_by(Invoice.date_facture.desc()).first()
            )
            new_statut = (
                "ACTIF"
                if last_inv and last_inv.date_facture and last_inv.date_facture > cutoff
                else "INACTIF"
            )
            if c.statut != new_statut:
                c.statut = new_statut
                updated += 1
        db.session.commit()
        return updated

    # ── Search ────────────────────────────────────────────────────────────

    @staticmethod
    def search(
        company_id: int,
        q: str = "",
        risk_level: str = "",
        statut: str = "",
        gouvernorat: str = "",
        nature_client: str = "",
        score_min: int = 0,
        score_max: int = 100,
        page: int = 1,
        per_page: int = 20,
        sort_by: str = "score_actuel",
        sort_dir: str = "desc",
    ):
        query = Client.query.filter_by(company_id=company_id)

        if q:
            like = f"%{q}%"
            query = query.filter(or_(
                Client.code_client.ilike(like),
                Client.nom.ilike(like),
                Client.email.ilike(like),
                Client.gouvernorat.ilike(like),
            ))
        if risk_level:
            query = query.filter(Client.risk_level == risk_level.upper())
        if statut:
            query = query.filter(Client.statut == statut.upper())
        if gouvernorat:
            query = query.filter(Client.gouvernorat.ilike(f"%{gouvernorat}%"))
        if nature_client:
            query = query.filter(Client.nature_client.ilike(f"%{nature_client}%"))

        # Recherche client: garder aussi les clients sans score encore calculé.
        # Avant, une recherche par code pouvait ne rien retourner si score_actuel = NULL.
        query = query.filter(or_(Client.score_actuel == None, Client.score_actuel >= score_min))
        query = query.filter(or_(Client.score_actuel == None, Client.score_actuel <= score_max))

        col = getattr(Client, sort_by, Client.score_actuel)
        query = query.order_by(col.desc() if sort_dir == "desc" else col.asc())

        return query.paginate(page=page, per_page=per_page, error_out=False)


    @staticmethod
    def top_risk_clients(company_id: int, limit: int = 20) -> list[dict]:
        """Retourne les clients les plus risqués pour l'onglet Top Client."""
        clients = (
            Client.query.filter_by(company_id=company_id)
            .order_by(Client.score_actuel.desc())
            .limit(limit)
            .all()
        )
        return [c.to_dict() for c in clients]

    # ── 360 Profile ───────────────────────────────────────────────────────

    @staticmethod
    def get_profile(client_id: int) -> dict:
        client = Client.query.get_or_404(client_id)

        score_hist = (
            ScoreHistory.query.filter_by(client_id=client_id)
            .order_by(ScoreHistory.predicted_at.desc()).limit(30).all()
        )
        last_preds = (
            Prediction.query.filter_by(client_id=client_id)
            .order_by(Prediction.predicted_at.desc()).limit(5).all()
        )
        payments = (
            PaymentHistory.query.filter_by(client_id=client_id)
            .order_by(PaymentHistory.date.desc()).limit(20).all()
        )
        invoices = (
            Invoice.query.filter_by(client_id=client_id)
            .order_by(Invoice.date_facture.desc()).limit(20).all()
        )
        active_alerts = (
            Alert.query.filter_by(client_id=client_id)
            .filter(Alert.resolved_at.is_(None)).all()
        )
        relances = (
            Relance.query.filter_by(client_id=client_id)
            .order_by(Relance.created_at.desc()).limit(10).all()
        )
        credit = CreditLimit.query.filter_by(client_id=client_id).first()

        pay_stats = _payment_stats(payments, invoices)
        commercial_behavior = _commercial_behavior(client, payments, invoices, pay_stats)
        timeline  = _build_timeline(last_preds, payments, relances)

        return {
            "client":              client.to_dict(),
            "score_history":       [s.to_dict() for s in score_hist],
            "last_predictions":    [p.to_dict() for p in last_preds],
            "payment_stats":       pay_stats,
            "commercial_behavior": commercial_behavior,
            "recent_payments":     [p.to_dict() for p in payments],
            "recent_invoices":     [i.to_dict() for i in invoices],
            "active_alerts":       [a.to_dict() for a in active_alerts],
            "recent_relances":     [r.to_dict() for r in relances],
            "credit":              credit.to_dict() if credit else None,
            "timeline":            timeline,
        }

    # ── Score history ──────────────────────────────────────────────────────

    @staticmethod
    def log_score(client: Client, risk_score: int, risk_level: str) -> None:
        sh = ScoreHistory(
            company_id=client.company_id,
            client_id=client.id,
            risk_score=risk_score,
            risk_level=risk_level,
        )
        db.session.add(sh)

    # ── Credit limit ──────────────────────────────────────────────────────

    @staticmethod
    def set_credit_limit(client: Client, plafond: float, user_id: int) -> CreditLimit:
        cl = CreditLimit.query.filter_by(client_id=client.id).first()
        if cl is None:
            cl = CreditLimit(client_id=client.id)
            db.session.add(cl)
        cl.plafond_credit = plafond
        cl.updated_by     = user_id
        client.plafond_credit = plafond
        db.session.flush()
        return cl

    # ── Alerts ────────────────────────────────────────────────────────────

    @staticmethod
    def check_and_create_alerts(client: Client, result: dict) -> list[Alert]:
        created = []
        checks = [
            (result["risk_score"] >= 80, "CRITICAL", "RISQUE_TRES_ELEVE",
             f"Score de risque très élevé : {result['risk_score']}/100"),
            (result["risk_score"] >= 60, "HIGH", "RISQUE_ELEVE",
             f"Score de risque élevé : {result['risk_score']}/100"),
            (result.get("retard_max", 0) > 60, "HIGH", "RETARD_CRITIQUE",
             "Retard maximum supérieur à 60 jours"),
            (
                client.total_impaye > client.plafond_credit * 0.9
                and client.plafond_credit > 0,
                "MEDIUM", "PLAFOND_BIENTOT_ATTEINT",
                "Utilisation crédit > 90% du plafond"
            ),
        ]
        for condition, severity, atype, message in checks:
            if not condition:
                continue
            existing = Alert.query.filter_by(
                client_id=client.id, type=atype
            ).filter(Alert.resolved_at.is_(None)).first()
            if existing:
                continue
            alert = Alert(
                company_id=client.company_id,
                client_id=client.id,
                type=atype, severity=severity, message=message,
            )
            db.session.add(alert)
            created.append(alert)
        return created

    # ── Relance ───────────────────────────────────────────────────────────

    @staticmethod
    def create_relance(
        client: Client, relance_type: str, message: str,
        montant_vise: float, user_id: int,
    ) -> Relance:
        r = Relance(
            company_id=client.company_id,
            client_id=client.id,
            type=relance_type.upper(),
            message=message,
            montant_vise=montant_vise,
            created_by=user_id,
        )
        db.session.add(r)
        db.session.flush()
        return r


# ── Private helpers ────────────────────────────────────────────────────────────

def _payment_stats(payments: list, invoices: list) -> dict:
    if not payments and not invoices:
        return {}
    total_montant = sum(p.montant for p in payments)
    avg_delai     = round(sum(p.delai for p in payments) / max(1, len(payments)), 1)
    nb_retards    = sum(1 for p in payments if p.delai > 0)
    modes: dict = {}
    for p in payments:
        modes[p.mode] = modes.get(p.mode, 0) + 1
    total_factures = sum(i.montant_facture for i in invoices)
    total_impaye   = sum(i.reste_a_payer   for i in invoices)
    nb_impayes     = sum(1 for i in invoices if i.statut == "IMPAYEE")
    return {
        "total_regle":    round(total_montant, 2),
        "avg_delai":      avg_delai,
        "nb_retards":     nb_retards,
        "modes_paiement": modes,
        "total_factures": round(total_factures, 2),
        "total_impaye":   round(total_impaye, 2),
        "nb_impayes":     nb_impayes,
        "taux_recouvrement": round(
            (total_montant / total_factures * 100) if total_factures > 0 else 0, 1
        ),
    }


def _commercial_behavior(client: Client, payments: list, invoices: list, pay_stats: dict) -> dict:
    total_factures = pay_stats.get("total_factures", 0) if pay_stats else 0
    total_regle = pay_stats.get("total_regle", 0) if pay_stats else 0
    ratio_paiement = round((total_regle / total_factures) if total_factures else 0, 3)
    nb_factures = len(invoices)
    nb_paiements = len(payments)
    montant_moy_facture = round((total_factures / nb_factures) if nb_factures else 0, 2)
    retard_moyen = pay_stats.get("avg_delai", 0) if pay_stats else 0

    if client.risk_level == "ÉLEVÉ":
        profil = "Client à risque élevé"
        recommandation = "Limiter les facilités de paiement et suivre les retards."
    elif client.risk_level == "MOYEN":
        profil = "Client à surveiller"
        recommandation = "Maintenir un suivi régulier du comportement de paiement."
    elif client.risk_level == "FAIBLE":
        profil = "Client fiable"
        recommandation = "Client favorable pour les conditions de crédit habituelles."
    else:
        profil = "Profil non évalué"
        recommandation = "Lancer une analyse après importation et entraînement du modèle."

    return {
        "profil": profil,
        "recommandation": recommandation,
        "ratio_paiement": ratio_paiement,
        "nb_factures": nb_factures,
        "nb_paiements": nb_paiements,
        "montant_moy_facture": montant_moy_facture,
        "retard_moyen": retard_moyen,
        "total_achats": round(total_factures, 2),
        "total_paiements": round(total_regle, 2),
        "total_retards": pay_stats.get("nb_retards", 0) if pay_stats else 0,
    }


def _build_timeline(preds, payments, relances) -> list[dict]:
    events = []
    for p in preds:
        events.append({
            "date":  p.predicted_at.isoformat() if p.predicted_at else None,
            "type":  "PREDICTION",
            "label": f"Analyse crédit — {p.label} ({p.risk_score}/100)",
            "color": "red" if p.risk_level == "ÉLEVÉ" else ("orange" if p.risk_level == "MOYEN" else "green"),
        })
    for p in payments:
        events.append({
            "date":  p.date.isoformat() if p.date else None,
            "type":  "PAIEMENT",
            "label": f"Paiement {p.montant:,.0f} TND — {p.mode} (délai: {p.delai}j)",
            "color": "blue",
        })
    for r in relances:
        events.append({
            "date":  r.created_at.isoformat() if r.created_at else None,
            "type":  "RELANCE",
            "label": f"Relance {r.type} — {r.statut}",
            "color": "purple",
        })
    return sorted(
        [e for e in events if e["date"]], key=lambda x: x["date"], reverse=True
    )[:50]

"""
models/__init__.py
SQLAlchemy ORM models for Système Intelligent de Scoring de Solvabilité Client.

Aligned with the UML class diagram from the rapport de fin d'études:
  Utilisateur, Admin, ResponsableFinancier, Client, Compte,
  HistoriquePaiement, Prediction, ModeleML, ExplicationSHAP,
  Dataset, HistoriqueSysteme.

Extra operational tables (Alert, Relance, CreditLimit, ScoreHistory,
Invoice, AuditLog) are kept for full system functionality.
"""
from __future__ import annotations

from datetime import datetime, timezone

from extensions import db


# ── Mixins ────────────────────────────────────────────────────────────────────

class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)


# ── Company ───────────────────────────────────────────────────────────────────

class Company(TimestampMixin, db.Model):
    __tablename__ = "companies"

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(200), nullable=False)
    slug        = db.Column(db.String(100), unique=True, nullable=False)
    email       = db.Column(db.String(200))
    phone       = db.Column(db.String(50))
    address     = db.Column(db.Text)
    is_active   = db.Column(db.Boolean, default=True)
    plan        = db.Column(db.String(50), default="STARTER")

    users    = db.relationship("User",    backref="company", lazy="dynamic")
    clients  = db.relationship("Client",  backref="company", lazy="dynamic")
    datasets = db.relationship("Dataset", backref="company", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "slug": self.slug,
            "email": self.email, "is_active": self.is_active,
        }


# ── Utilisateur (classe de base UML) ─────────────────────────────────────────
# Maps to the rapport's "Utilisateur" class with attributes:
#   id, nom, email, motDePasse, role
# and method: s'authentifier()

class User(TimestampMixin, db.Model):
    """Utilisateur — classe de base UML (rapport section 2.5.1)."""
    __tablename__ = "users"
    __table_args__ = (db.UniqueConstraint("company_id", "email"),)

    id            = db.Column(db.Integer, primary_key=True)
    company_id    = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    email         = db.Column(db.String(200), nullable=False)         # email
    password_hash = db.Column(db.String(256), nullable=False)         # motDePasse (hashed)
    nom           = db.Column(db.String(100))                          # nom
    prenom        = db.Column(db.String(100))
    role          = db.Column(db.String(50), default="USER")           # role: ADMIN | MANAGER | ANALYST | USER
    is_active     = db.Column(db.Boolean, default=True)
    last_login    = db.Column(db.DateTime(timezone=True))

    # UML method: s'authentifier() → implemented in auth_routes.py /login
    def s_authentifier(self, password_hash_bcrypt, raw_password) -> bool:
        """Vérifie les identifiants — proxy pour auth_routes.login."""
        from extensions import bcrypt
        return bcrypt.check_password_hash(password_hash_bcrypt, raw_password)

    def full_name(self):
        return f"{self.prenom or ''} {self.nom or ''}".strip() or self.email

    def to_dict(self):
        return {
            "id": self.id, "company_id": self.company_id,
            "email": self.email, "nom": self.nom, "prenom": self.prenom,
            "role": self.role, "is_active": self.is_active,
            "full_name": self.full_name(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat(),
        }


# ── Client ────────────────────────────────────────────────────────────────────
# Maps to the rapport's "Client" class with attributes:
#   idClient, adresse, telephone, secteur, scoreRisque, niveauSolvabilite
# and method: consulterInformations()

class Client(TimestampMixin, db.Model):
    """Client — classe UML (rapport section 2.5.1)."""
    __tablename__ = "clients"
    __table_args__ = (db.UniqueConstraint("company_id", "code_client"),)

    id            = db.Column(db.Integer, primary_key=True)           # idClient
    company_id    = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    code_client   = db.Column(db.String(100), nullable=False)
    nom           = db.Column(db.String(200))
    email         = db.Column(db.String(200))
    telephone     = db.Column(db.String(50))                           # telephone
    gouvernorat   = db.Column(db.String(100))                          # adresse/secteur géographique
    nature_client = db.Column(db.String(100))                          # secteur d'activité
    statut        = db.Column(db.String(50), default="ACTIF")

    # Scores de risque (rapport: scoreRisque, niveauSolvabilite)
    score_actuel     = db.Column(db.Float, default=0.0)                # scoreRisque
    risk_level       = db.Column(db.String(50), default="INCONNU")     # niveauSolvabilite
    derniere_analyse = db.Column(db.DateTime(timezone=True))

    # Données financières (rapport: Compte.totalAchats, totalPaiements, totalRetards)
    total_impaye    = db.Column(db.Float, default=0.0)
    credit_utilise  = db.Column(db.Float, default=0.0)
    plafond_credit  = db.Column(db.Float, default=50000.0)
    anciennete      = db.Column(db.Integer, default=0)                 # mois

    # Dernières features ML pour re-scoring
    last_features   = db.Column(db.JSON)

    predictions  = db.relationship("Prediction",    backref="client", lazy="dynamic")
    score_hist   = db.relationship("ScoreHistory",  backref="client", lazy="dynamic")
    payments     = db.relationship("PaymentHistory", backref="client", lazy="dynamic")
    invoices     = db.relationship("Invoice",        backref="client", lazy="dynamic")
    alerts       = db.relationship("Alert",          backref="client", lazy="dynamic")
    relances     = db.relationship("Relance",        backref="client", lazy="dynamic")

    # UML method: consulterInformations() (rapport section 2.5.2)
    def consulterInformations(self) -> dict:
        """Retourne les informations complètes du client."""
        return self.to_dict()

    def to_dict(self):
        solvabilite = "INCONNU"
        if self.risk_level in ("FAIBLE", "MOYEN"):
            solvabilite = "SOLVABLE"
        elif self.risk_level == "ÉLEVÉ":
            solvabilite = "NON-SOLVABLE"

        return {
            "id": self.id, "company_id": self.company_id,
            "code_client": self.code_client, "nom": self.nom,
            "email": self.email, "telephone": self.telephone,
            "gouvernorat": self.gouvernorat, "nature_client": self.nature_client,
            "statut": self.statut,
            "score_actuel": self.score_actuel, "score_risque": self.score_actuel,
            "risk_level": self.risk_level, "solvabilite": solvabilite,
            "derniere_analyse": self.derniere_analyse.isoformat() if self.derniere_analyse else None,
            "total_impaye": self.total_impaye, "credit_utilise": self.credit_utilise,
            "plafond_credit": self.plafond_credit, "anciennete": self.anciennete,
            "created_at": self.created_at.isoformat(),
        }


# ── Compte ────────────────────────────────────────────────────────────────────
# Maps to the rapport's "Compte" class with attributes:
#   idCompte, dateCreation, statutCompte, totalAchats, totalPaiements, totalRetards

class Compte(TimestampMixin, db.Model):
    """Compte — classe UML (rapport section 2.5.1).
    Résumé financier agrégé du client.
    """
    __tablename__ = "comptes"

    id              = db.Column(db.Integer, primary_key=True)          # idCompte
    client_id       = db.Column(db.Integer, db.ForeignKey("clients.id"), unique=True, nullable=False)
    company_id      = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    date_creation   = db.Column(db.DateTime(timezone=True),             # dateCreation
                                default=lambda: datetime.now(timezone.utc))
    statut_compte   = db.Column(db.String(50), default="ACTIF")         # statutCompte
    total_achats    = db.Column(db.Float, default=0.0)                  # totalAchats
    total_paiements = db.Column(db.Float, default=0.0)                  # totalPaiements
    total_retards   = db.Column(db.Integer, default=0)                  # totalRetards

    client = db.relationship("Client", backref=db.backref("compte", uselist=False))

    def to_dict(self):
        return {
            "id": self.id, "client_id": self.client_id,
            "date_creation": self.date_creation.isoformat() if self.date_creation else None,
            "statut_compte": self.statut_compte,
            "total_achats": self.total_achats,
            "total_paiements": self.total_paiements,
            "total_retards": self.total_retards,
        }


# ── Dataset ───────────────────────────────────────────────────────────────────
# Maps to the rapport's "Dataset" class:
#   idDataset, nomFichier, dateImportation, nombreLignes
# Methods: importerDataset(), nettoyerDataset()

class Dataset(TimestampMixin, db.Model):
    """Dataset — classe UML (rapport section 2.5.1)."""
    __tablename__ = "datasets"

    id          = db.Column(db.Integer, primary_key=True)              # idDataset
    company_id  = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    filename    = db.Column(db.String(300), nullable=False)             # nomFichier
    file_path   = db.Column(db.String(500))
    file_size   = db.Column(db.Integer)
    nb_rows     = db.Column(db.Integer)                                  # nombreLignes
    nb_cols     = db.Column(db.Integer)

    # Statut pipeline
    status            = db.Column(db.String(50), default="UPLOADED")
    # UPLOADED → VALIDATING → PROCESSING → COMPLETED | FAILED
    training_progress = db.Column(db.Integer, default=0)
    training_step     = db.Column(db.String(200))
    error_message     = db.Column(db.Text)
    celery_task_id    = db.Column(db.String(200))
    validation_report = db.Column(db.JSON)

    models = db.relationship("MLModel", backref="dataset", lazy="dynamic")

    # UML method: importerDataset() → implemented in dataset_routes.py /upload
    def importerDataset(self) -> dict:
        """Retourne les infos du dataset importé."""
        return self.to_dict()

    # UML method: nettoyerDataset() → implemented in ml_preprocessing.clean_and_engineer()
    def nettoyerDataset(self) -> str:
        """Lance le nettoyage du dataset — délégué au pipeline ML."""
        return f"Dataset {self.filename} — nettoyage via ml_preprocessing.clean_and_engineer()"

    @property
    def resolved_file_path(self) -> str:
        """Résout le chemin relatif vers un chemin absolu."""
        import os
        path = self.file_path
        if not path:
            return ""
        if os.path.isabs(path):
            return path
        models_dir  = os.path.dirname(os.path.abspath(__file__))
        backend_base = os.path.abspath(os.path.join(models_dir, ".."))
        resolved = os.path.abspath(os.path.join(backend_base, path))
        if os.path.exists(resolved):
            return resolved
        root_base = os.path.abspath(os.path.join(backend_base, ".."))
        root_resolved = os.path.abspath(os.path.join(root_base, path))
        if os.path.exists(root_resolved):
            return root_resolved
        return resolved

    def to_dict(self):
        return {
            "id": self.id, "company_id": self.company_id,
            "filename": self.filename, "file_size": self.file_size,
            "nb_rows": self.nb_rows, "nb_cols": self.nb_cols,
            "status": self.status,
            "training_progress": self.training_progress,
            "training_step": self.training_step,
            "error_message": self.error_message,
            "celery_task_id": self.celery_task_id,
            "validation_report": self.validation_report,
            "created_at": self.created_at.isoformat(),
        }


# ── ModeleML ──────────────────────────────────────────────────────────────────
# Maps to the rapport's "ModeleML" class:
#   idModele, nomModele, version, precision, dateEntrainement
# Methods: entrainerModele(), evaluerModele(), sauvegarderModele()

class MLModel(TimestampMixin, db.Model):
    """ModeleML — classe UML (rapport section 2.5.1)."""
    __tablename__ = "ml_models"

    id            = db.Column(db.Integer, primary_key=True)            # idModele
    company_id    = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    dataset_id    = db.Column(db.Integer, db.ForeignKey("datasets.id"))
    trained_by    = db.Column(db.Integer, db.ForeignKey("users.id"))

    model_name    = db.Column(db.String(100))                           # nomModele: RF | XGBoost | LightGBM
    version       = db.Column(db.Integer, default=1)                    # version
    is_active     = db.Column(db.Boolean, default=False)

    # Métriques (rapport: precision)
    accuracy      = db.Column(db.Float)
    precision     = db.Column(db.Float)                                  # precision
    recall        = db.Column(db.Float)
    f1_score      = db.Column(db.Float)
    roc_auc       = db.Column(db.Float)
    threshold     = db.Column(db.Float, default=0.5)
    date_entrainement = db.Column(db.DateTime(timezone=True))            # dateEntrainement

    artifact_paths      = db.Column(db.JSON)
    feature_importances = db.Column(db.JSON)
    all_models_results  = db.Column(db.JSON)

    # UML methods (rapport section 2.5.2)
    def entrainerModele(self) -> str:
        """Lance l'entraînement — délégué à ml_trainer.run_training_pipeline()."""
        return f"Modèle {self.model_name} v{self.version} — entraînement via dataset_routes.start_training()"

    def evaluerModele(self) -> dict:
        """Retourne les métriques d'évaluation."""
        return {
            "accuracy": self.accuracy, "precision": self.precision,
            "recall": self.recall, "f1_score": self.f1_score,
            "roc_auc": self.roc_auc, "threshold": self.threshold,
        }

    def sauvegarderModele(self) -> str:
        """Sauvegarde les artefacts — délégué à ml_pipeline._save()."""
        return f"Artefacts sauvegardés dans : {self.artifact_paths}"

    def to_dict(self):
        return {
            "id": self.id, "company_id": self.company_id,
            "dataset_id": self.dataset_id, "model_name": self.model_name,
            "version": self.version, "is_active": self.is_active,
            "metrics": {
                "accuracy": self.accuracy, "precision": self.precision,
                "recall": self.recall, "f1_score": self.f1_score,
                "roc_auc": self.roc_auc, "threshold": self.threshold,
            },
            "date_entrainement": self.date_entrainement.isoformat() if self.date_entrainement else None,
            "artifact_paths": self.artifact_paths,
            "feature_importances": self.feature_importances,
            "all_models_results": self.all_models_results,
            "created_at": self.created_at.isoformat(),
        }


# ── Prediction ────────────────────────────────────────────────────────────────
# Maps to the rapport's "Prediction" class:
#   idPrediction, datePrediction, scoreRisque, resultat
# Methods: predireSolvabilite(), genererScore()

class Prediction(db.Model):
    """Prediction — classe UML (rapport section 2.5.1)."""
    __tablename__ = "predictions"

    id           = db.Column(db.Integer, primary_key=True)             # idPrediction
    company_id   = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    client_id    = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    model_id     = db.Column(db.Integer, db.ForeignKey("ml_models.id"))
    predicted_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    predicted_at = db.Column(db.DateTime(timezone=True),               # datePrediction
                             default=lambda: datetime.now(timezone.utc))

    label            = db.Column(db.String(50))    # resultat: SOLVABLE | NON-SOLVABLE
    risk_score       = db.Column(db.Float)          # scoreRisque
    risk_level       = db.Column(db.String(50))
    probability      = db.Column(db.Float)
    probability_risk = db.Column(db.Float)
    threshold_used   = db.Column(db.Float)
    ai_summary       = db.Column(db.Text)
    shap_factors     = db.Column(db.JSON)
    input_data       = db.Column(db.JSON)

    # UML methods (rapport section 2.5.2)
    def predireSolvabilite(self) -> str:
        """Retourne le label de solvabilité prédit."""
        return self.label

    def genererScore(self) -> float:
        """Retourne le score de risque calculé."""
        return self.risk_score

    def to_dict(self):
        return {
            "id": self.id, "company_id": self.company_id,
            "client_id": self.client_id, "model_id": self.model_id,
            "predicted_at": self.predicted_at.isoformat() if self.predicted_at else None,
            "label": self.label, "risk_score": self.risk_score,
            "risk_level": self.risk_level, "probability": self.probability,
            "probability_risk": self.probability_risk,
            "ai_summary": self.ai_summary, "shap_factors": self.shap_factors,
        }


# ── ExplicationSHAP ───────────────────────────────────────────────────────────
# Maps to the rapport's "ExplicationSHAP" class:
#   idExplication, variableImportante, impact, description
# Methods: genererExplication(), afficherExplication()

class ExplicationSHAP(db.Model):
    """ExplicationSHAP — classe UML (rapport section 2.5.1)."""
    __tablename__ = "explications_shap"

    id                  = db.Column(db.Integer, primary_key=True)      # idExplication
    prediction_id       = db.Column(db.Integer, db.ForeignKey("predictions.id"), nullable=False)
    variable_importante = db.Column(db.String(200))                     # variableImportante
    impact              = db.Column(db.Float)                           # impact (valeur SHAP)
    description         = db.Column(db.Text)                            # description

    prediction = db.relationship("Prediction", backref="explications")

    # UML methods (rapport section 2.5.2)
    def genererExplication(self) -> dict:
        """Retourne le détail de l'explication SHAP."""
        return {
            "variable": self.variable_importante,
            "impact": self.impact,
            "description": self.description,
        }

    def afficherExplication(self) -> str:
        """Retourne un résumé lisible de l'explication."""
        sign = "↑" if (self.impact or 0) > 0 else "↓"
        return f"{sign} {self.variable_importante} : impact = {self.impact:.4f}"

    def to_dict(self):
        return {
            "id": self.id, "prediction_id": self.prediction_id,
            "variable_importante": self.variable_importante,
            "impact": self.impact, "description": self.description,
        }


# ── HistoriquePaiement ────────────────────────────────────────────────────────
# Maps to the rapport's "HistoriquePaiement" class:
#   idPaiement, datePaiement, montant, retard, statutPaiement
# Methods: ajouterPaiement(), consulterHistorique()

class PaymentHistory(db.Model):
    """HistoriquePaiement — classe UML (rapport section 2.5.1)."""
    __tablename__ = "payment_history"

    id          = db.Column(db.Integer, primary_key=True)              # idPaiement
    company_id  = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    client_id   = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    montant     = db.Column(db.Float, nullable=False)                  # montant
    mode        = db.Column(db.String(100))
    date        = db.Column(db.DateTime(timezone=True))                # datePaiement
    delai       = db.Column(db.Integer, default=0)                     # retard (jours)
    statut_paiement = db.Column(db.String(50), default="REGLE")        # statutPaiement
    reference   = db.Column(db.String(200))

    # UML methods (rapport section 2.5.2)
    def ajouterPaiement(self) -> dict:
        """Retourne les données du paiement ajouté."""
        return self.to_dict()

    def consulterHistorique(self) -> str:
        """Délégué à client_service.get_profile() — historique paiements."""
        return f"Historique paiement client #{self.client_id}"

    def to_dict(self):
        return {
            "id": self.id, "client_id": self.client_id,
            "montant": self.montant, "mode": self.mode,
            "date": self.date.isoformat() if self.date else None,
            "delai": self.delai,
            "statut_paiement": self.statut_paiement,
            "reference": self.reference,
        }


# ── HistoriqueSysteme ─────────────────────────────────────────────────────────
# Maps to the rapport's "HistoriqueSysteme" class:
#   idHistorique, action, dateAction, description
# Methods: enregistrerAction(), afficherHistorique()

class AuditLog(db.Model):
    """HistoriqueSysteme / AuditLog — classe UML (rapport section 2.5.1)."""
    __tablename__ = "audit_logs"

    id          = db.Column(db.Integer, primary_key=True)              # idHistorique
    company_id  = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"))
    action      = db.Column(db.String(100), nullable=False)             # action
    resource    = db.Column(db.String(100))
    resource_id = db.Column(db.String(100))
    detail      = db.Column(db.JSON)                                    # description
    ip_address  = db.Column(db.String(50))
    user_agent  = db.Column(db.String(256))
    created_at  = db.Column(db.DateTime(timezone=True),                 # dateAction
                            default=lambda: datetime.now(timezone.utc), nullable=False)

    # UML methods (rapport section 2.5.2)
    def enregistrerAction(self) -> dict:
        """Retourne l'action enregistrée."""
        return self.to_dict()

    def afficherHistorique(self) -> str:
        """Résumé lisible de l'action."""
        return f"[{self.created_at}] {self.action} — ressource: {self.resource}/{self.resource_id}"

    def to_dict(self):
        return {
            "id": self.id, "user_id": self.user_id,
            "action": self.action, "resource": self.resource,
            "resource_id": self.resource_id, "detail": self.detail,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat(),
        }


# ── Score history ─────────────────────────────────────────────────────────────

class ScoreHistory(db.Model):
    __tablename__ = "score_history"

    id          = db.Column(db.Integer, primary_key=True)
    company_id  = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    client_id   = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    risk_score  = db.Column(db.Float, nullable=False)
    risk_level  = db.Column(db.String(50))
    predicted_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id, "client_id": self.client_id,
            "risk_score": self.risk_score, "risk_level": self.risk_level,
            "predicted_at": self.predicted_at.isoformat() if self.predicted_at else None,
        }


# ── Invoice ───────────────────────────────────────────────────────────────────

class Invoice(db.Model):
    __tablename__ = "invoices"

    id              = db.Column(db.Integer, primary_key=True)
    company_id      = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    client_id       = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    numero_facture  = db.Column(db.String(100))
    montant_facture = db.Column(db.Float, nullable=False)
    montant_regle   = db.Column(db.Float, default=0.0)
    reste_a_payer   = db.Column(db.Float)
    date_facture    = db.Column(db.DateTime(timezone=True))
    date_echeance   = db.Column(db.DateTime(timezone=True))
    statut          = db.Column(db.String(50), default="EN_ATTENTE")

    def to_dict(self):
        return {
            "id": self.id, "client_id": self.client_id,
            "numero_facture": self.numero_facture,
            "montant_facture": self.montant_facture,
            "montant_regle": self.montant_regle,
            "reste_a_payer": self.reste_a_payer,
            "date_facture": self.date_facture.isoformat() if self.date_facture else None,
            "date_echeance": self.date_echeance.isoformat() if self.date_echeance else None,
            "statut": self.statut,
        }


# ── Alert ─────────────────────────────────────────────────────────────────────

class Alert(TimestampMixin, db.Model):
    __tablename__ = "alerts"

    id          = db.Column(db.Integer, primary_key=True)
    company_id  = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    client_id   = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    type        = db.Column(db.String(100))
    severity    = db.Column(db.String(50))
    message     = db.Column(db.Text)
    resolved_at = db.Column(db.DateTime(timezone=True))
    resolved_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    def to_dict(self):
        return {
            "id": self.id, "company_id": self.company_id, "client_id": self.client_id,
            "type": self.type, "severity": self.severity, "message": self.message,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "created_at": self.created_at.isoformat(),
        }


# ── Relance ───────────────────────────────────────────────────────────────────

class Relance(TimestampMixin, db.Model):
    __tablename__ = "relances"

    id           = db.Column(db.Integer, primary_key=True)
    company_id   = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    client_id    = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    type         = db.Column(db.String(50))
    message      = db.Column(db.Text)
    montant_vise = db.Column(db.Float)
    statut       = db.Column(db.String(50), default="PLANIFIEE")
    created_by   = db.Column(db.Integer, db.ForeignKey("users.id"))

    def to_dict(self):
        return {
            "id": self.id, "client_id": self.client_id,
            "type": self.type, "message": self.message,
            "montant_vise": self.montant_vise, "statut": self.statut,
            "created_at": self.created_at.isoformat(),
        }


# ── CreditLimit ───────────────────────────────────────────────────────────────

class CreditLimit(TimestampMixin, db.Model):
    __tablename__ = "credit_limits"

    id             = db.Column(db.Integer, primary_key=True)
    client_id      = db.Column(db.Integer, db.ForeignKey("clients.id"), unique=True)
    plafond_credit = db.Column(db.Float, default=50000.0)
    updated_by     = db.Column(db.Integer, db.ForeignKey("users.id"))

    def to_dict(self):
        return {
            "id": self.id, "client_id": self.client_id,
            "plafond_credit": self.plafond_credit,
            "updated_at": self.updated_at.isoformat(),
        }

# ── UML compatibility layer ─────────────────────────────────────────────────
# The conceptual chapter names the domain classes in French.  The application
# keeps the operational table names used by Flask/SQLAlchemy, while exposing
# French aliases and methods so the backend behavior stays aligned with the
# conception without breaking the existing routes.

def _user_gerer_utilisateurs(self):
    return "Gestion des utilisateurs via /api/auth/users"

def _user_consulter_historique_systeme(self):
    return "Consultation de l'historique système via /api/dashboard/historique-systeme"

def _user_importer_dataset(self):
    return "Importation de dataset via /api/datasets/upload"

def _user_gerer_modeles_ml(self):
    return "Gestion des modèles ML via /api/models"

def _user_visualiser_resultats_entrainement(self):
    return "Visualisation des résultats d'entraînement via /api/models"

def _user_rechercher_client(self):
    return "Recherche client via /api/clients?q=..."

def _user_consulter_profil_client(self):
    return "Profil client via /api/clients/<id>/profile"

def _user_analyser_historique_paiement(self):
    return "Analyse historique paiement via /api/clients/<id>/historique-paiement"

def _user_analyser_comportement_commercial(self):
    return "Analyse comportement commercial via /api/clients/<id>/comportement-commercial"

def _user_predire_solvabilite(self):
    return "Résultats de solvabilité via /api/predict/solvabilite"

def _user_consulter_score_risque(self):
    return "Score de risque via /api/clients/<id>/score"

def _user_consulter_explications_shap(self):
    return "Explications SHAP via /api/clients/<id>/explications-shap"

User.gererUtilisateurs = _user_gerer_utilisateurs
User.consulterHistoriqueSysteme = _user_consulter_historique_systeme
User.importerDataset = _user_importer_dataset
User.gererModelesML = _user_gerer_modeles_ml
User.visualiserResultatsEntrainement = _user_visualiser_resultats_entrainement
User.rechercherClient = _user_rechercher_client
User.consulterProfilClient = _user_consulter_profil_client
User.analyserHistoriquePaiement = _user_analyser_historique_paiement
User.analyserComportementCommercial = _user_analyser_comportement_commercial
User.predireSolvabilite = _user_predire_solvabilite
User.consulterScoreRisque = _user_consulter_score_risque
User.consulterExplicationsSHAP = _user_consulter_explications_shap

# French class aliases from the UML diagram / relational model.
Utilisateur = User
Admin = User
ResponsableFinancier = User
ModeleML = MLModel
HistoriquePaiement = PaymentHistory
HistoriqueSysteme = AuditLog

def _ml_generer_prediction(self):
    return "Génération des prédictions via PredictionService.predict()"

MLModel.genererPrediction = _ml_generer_prediction

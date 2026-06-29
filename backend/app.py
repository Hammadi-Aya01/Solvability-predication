"""
app.py
Flask application factory for SolvAI Credit Scoring Platform.
"""
from __future__ import annotations

import os
from flask import Flask, jsonify
from flask_cors import CORS

from config import get_config
from extensions import db, migrate, jwt, cache, limiter, bcrypt


def create_app(config_name: str | None = None) -> Flask:
    """Application factory."""
    app = Flask(__name__)

    # ── Config ────────────────────────────────────────────────────────────
    cfg = get_config(config_name or os.getenv("FLASK_ENV", "development"))
    app.config.from_object(cfg)

    # ── Extensions ────────────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cache.init_app(app)
    limiter.init_app(app)
    bcrypt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS", "*")}})

    # ── Create upload/model directories ───────────────────────────────────
    for folder in [
        app.config["UPLOAD_FOLDER"],
        app.config["MODEL_DIR"],
        app.config["EXPORT_FOLDER"],
        "logs",
    ]:
        os.makedirs(folder, exist_ok=True)

    # ── Register blueprints ───────────────────────────────────────────────
    from routes.auth_routes import auth_bp
    from routes.client_routes import client_bp
    from routes.dashboard_routes import dashboard_bp
    from routes.dataset_routes import dataset_bp
    from routes.model_routes import model_bp
    from routes.predict_routes import predict_bp

    app.register_blueprint(auth_bp,      url_prefix="/api/auth")
    app.register_blueprint(client_bp,    url_prefix="/api/clients")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    app.register_blueprint(dataset_bp,   url_prefix="/api/datasets")
    app.register_blueprint(model_bp,     url_prefix="/api/models")
    app.register_blueprint(predict_bp,   url_prefix="/api/predict")

    # ── Global error handlers ─────────────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "message": str(e)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "Unauthorized"}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Forbidden"}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(422)
    def unprocessable(e):
        return jsonify({"error": "Unprocessable entity", "message": str(e)}), 422

    @app.errorhandler(429)
    def too_many_requests(e):
        return jsonify({"error": "Too many requests"}), 429

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return jsonify({"error": "Internal server error"}), 500

    # ── JWT error handlers ────────────────────────────────────────────────
    from flask_jwt_extended import exceptions as jwt_exc

    @jwt.expired_token_loader
    def expired_token(_jwt_header, _jwt_payload):
        return jsonify({"error": "Token expiré"}), 401

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return jsonify({"error": f"Token invalide: {reason}"}), 401

    @jwt.unauthorized_loader
    def missing_token(reason):
        return jsonify({"error": f"Token manquant: {reason}"}), 401

    # ── Health check ──────────────────────────────────────────────────────
    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "version": "1.0.0"})

    # ── Database bootstrap / local SQLite schema repair ─────────────────
    # db.create_all() creates missing tables.  The small schema repair below
    # adds missing columns when an old local SQLite database is reused after
    # the code evolved.  This keeps the implementation aligned with the
    # rapport's classes without asking the user to run manual SQL commands.
    with app.app_context():
        db.create_all()
        _ensure_sqlite_schema(app)
        _try_load_active_model(app)

    # ── CLI Commands ──────────────────────────────────────────────────────
    import click
    import re
    @app.cli.command("create-company")
    @click.option("--name", required=True, help="Nom de l'entreprise")
    @click.option("--manager-name", required=True, help="Nom complet du responsable")
    @click.option("--email", required=True, help="Adresse e-mail professionnelle")
    @click.option("--password", required=True, help="Mot de passe temporaire")
    @click.option("--slug", help="Identifiant de l'entreprise (slug unique). Si omis, généré automatiquement.")
    def create_company_cli(name, manager_name, email, password, slug):
        """Crée une nouvelle entreprise et son administrateur principal."""
        from models import Company, User
        from extensions import db, bcrypt

        # Ensure all database tables exist (handles SQLite auto-creation)
        db.create_all()

        # check if user with email already exists
        if User.query.filter_by(email=email.lower()).first():
            click.echo(f"Erreur : L'adresse e-mail {email} est déjà utilisée.")
            return

        # Generate slug if not provided
        if not slug:
            slug = re.sub(r"[^a-z0-9]", "-", name.lower())[:50]
            slug = slug.strip("-")

        # Check if slug exists
        if Company.query.filter_by(slug=slug).first():
            from datetime import datetime
            slug = f"{slug}-{datetime.now().strftime('%f')[:6]}"

        company = Company(
            name=name,
            slug=slug,
            email=email.lower()
        )
        db.session.add(company)
        db.session.flush()

        # Split manager name into prenom and nom
        parts = manager_name.strip().split(" ", 1)
        prenom = parts[0] if len(parts) > 0 else ""
        nom = parts[1] if len(parts) > 1 else ""

        user = User(
            company_id=company.id,
            email=email.lower(),
            password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
            nom=nom,
            prenom=prenom,
            role="ADMIN",
        )
        db.session.add(user)
        db.session.commit()

        click.echo("Compte administrateur créé avec succès !")
        click.echo(f"  Nom de l'entreprise: {company.name}")
        click.echo(f"  Identifiant de l'entreprise (slug): {company.slug}")
        click.echo(f"  Responsable: {user.prenom} {user.nom}")
        click.echo(f"  Adresse e-mail: {user.email}")
        click.echo(f"  Mot de passe temporaire: {password}")



    @app.cli.command("seed-admin")
    @click.option("--email", required=True, help="Email de l'administrateur")
    @click.option("--password", required=True, help="Mot de passe")
    @click.option("--company", default="OneByte Solutions", help="Nom de l'entreprise")
    def seed_admin_cli(email, password, company):
        """Crée ou met à jour rapidement un compte administrateur local."""
        from models import Company, User
        from extensions import db, bcrypt
        import re

        db.create_all()
        email_l = email.lower().strip()
        slug = re.sub(r"[^a-z0-9]", "-", company.lower()).strip("-") or "company"

        comp = Company.query.filter_by(slug=slug).first()
        if comp is None:
            comp = Company(name=company, slug=slug, email=email_l)
            db.session.add(comp)
            db.session.flush()

        user = User.query.filter_by(email=email_l).first()
        if user is None:
            user = User(
                company_id=comp.id,
                email=email_l,
                password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
                prenom="Aya",
                nom="Admin",
                role="ADMIN",
            )
            db.session.add(user)
            click.echo("Admin created")
        else:
            user.company_id = comp.id
            user.role = "ADMIN"
            user.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
            click.echo("Admin updated")

        db.session.commit()
        click.echo(f"Email: {email_l}")
        click.echo(f"Password: {password}")

    return app



def _ensure_sqlite_schema(app: Flask) -> None:
    """Add missing columns for an existing local SQLite DB.

    This is intentionally conservative: it only runs for SQLite and only
    executes ALTER TABLE ADD COLUMN when the table exists and the column is
    absent. It fixes old local DB files after the code evolves.
    """
    uri = str(app.config.get("SQLALCHEMY_DATABASE_URI", ""))
    if not uri.startswith("sqlite"):
        return
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())
        desired = {
            "ml_models": {
                "date_entrainement": "DATETIME",
                "artifact_paths": "JSON",
                "feature_importances": "JSON",
                "all_models_results": "JSON",
                "threshold": "FLOAT",
                "roc_auc": "FLOAT",
                "f1_score": "FLOAT",
                "recall": "FLOAT",
                "precision": "FLOAT",
                "accuracy": "FLOAT",
                "is_active": "BOOLEAN",
                "version": "INTEGER",
                "model_name": "VARCHAR(100)",
                "trained_by": "INTEGER",
                "dataset_id": "INTEGER",
            },
            "datasets": {
                "training_progress": "INTEGER",
                "training_step": "VARCHAR(200)",
                "error_message": "TEXT",
                "celery_task_id": "VARCHAR(200)",
                "validation_report": "JSON",
                "nb_rows": "INTEGER",
                "nb_cols": "INTEGER",
                "file_size": "INTEGER",
                "file_path": "VARCHAR(500)",
                "status": "VARCHAR(50)",
            },
            "clients": {
                "score_actuel": "FLOAT",
                "risk_level": "VARCHAR(50)",
                "derniere_analyse": "DATETIME",
                "total_impaye": "FLOAT",
                "credit_utilise": "FLOAT",
                "plafond_credit": "FLOAT",
                "anciennete": "INTEGER",
                "last_features": "JSON",
            },
            "predictions": {
                "risk_score": "FLOAT",
                "risk_level": "VARCHAR(50)",
                "probability": "FLOAT",
                "probability_risk": "FLOAT",
                "threshold_used": "FLOAT",
                "ai_summary": "TEXT",
                "shap_factors": "JSON",
                "input_data": "JSON",
            },
        }
        with db.engine.begin() as conn:
            for table, cols in desired.items():
                if table not in tables:
                    continue
                existing = {c["name"] for c in inspector.get_columns(table)}
                for col, sql_type in cols.items():
                    if col not in existing:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {sql_type}"))
                        app.logger.info("SQLite schema repaired: added %s.%s", table, col)
    except Exception as exc:
        app.logger.warning("SQLite schema repair skipped: %s", exc)

def _try_load_active_model(app: Flask) -> None:
    """Attempt to load the active model at startup (non-fatal if unavailable)."""
    try:
        from models import MLModel
        with app.app_context():
            active = MLModel.query.filter_by(is_active=True).first()
            if active and active.artifact_paths:
                from services.prediction_service import PredictionService
                PredictionService.load_active_model(active)
                app.logger.info(f"Active model loaded: {active.model_name} v{active.version}")
    except Exception as e:
        app.logger.warning(f"Could not load active model at startup: {e}")


if __name__ == "__main__":
    application = create_app()
    application.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_ENV") == "development",
    )

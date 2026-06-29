"""
routes/auth_routes.py
Authentication: register, login, refresh, logout, profile.
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    get_jwt, get_jwt_identity, jwt_required,
)

from extensions import db, bcrypt
from models import User, Company, AuditLog
from security import (
    current_user_id, current_company_id, current_role,
    block_token, validate_password_strength, admin_required,
)
from services.audit_service import log_action

auth_bp = Blueprint("auth", __name__)


# ── Register ──────────────────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["POST"])
def register():
    """Create a new company + admin user."""
    data = request.get_json(force=True) or {}

    from flask import current_app
    reg_secret = current_app.config.get("REGISTRATION_SECRET")
    if reg_secret and not current_app.config.get("TESTING"):
        client_secret = request.headers.get("X-Registration-Secret") or data.get("registration_secret")
        if client_secret != reg_secret:
            return jsonify({"error": "La création de compte administrateur est restreinte à l'équipe technique"}), 403

    required = ["company_name", "email", "password"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Champs requis: {missing}"}), 400

    # Password strength
    issues = validate_password_strength(data["password"])
    if issues:
        return jsonify({"error": issues[0]}), 400

    # Email uniqueness
    if User.query.filter_by(email=data["email"].lower()).first():
        return jsonify({"error": "Email déjà utilisé"}), 409

    # Slug
    import re
    slug = re.sub(r"[^a-z0-9]", "-", data["company_name"].lower())[:50]
    if Company.query.filter_by(slug=slug).first():
        slug = f"{slug}-{datetime.now().strftime('%f')[:6]}"

    company = Company(
        name=data["company_name"],
        slug=slug,
        email=data.get("company_email", data["email"]),
    )
    db.session.add(company)
    db.session.flush()

    user = User(
        company_id=company.id,
        email=data["email"].lower(),
        password_hash=bcrypt.generate_password_hash(data["password"]).decode("utf-8"),
        nom=data.get("nom", ""),
        prenom=data.get("prenom", ""),
        role="ADMIN",
    )
    db.session.add(user)
    db.session.commit()

    access  = _make_access_token(user)
    refresh = create_refresh_token(identity=str(user.id))

    return jsonify({
        "message": "Compte créé avec succès",
        "access_token": access,
        "refresh_token": refresh,
        "user": user.to_dict(),
        "company": company.to_dict(),
    }), 201


# ── Login ─────────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True) or {}
    email    = (data.get("email") or data.get("login") or "").lower().strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Login/email et mot de passe requis"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({"error": "Identifiants incorrects"}), 401

    if not user.is_active:
        return jsonify({"error": "Compte désactivé"}), 403

    user.last_login = datetime.now(timezone.utc)
    db.session.commit()

    log_action(user.company_id, user.id, "LOGIN", "user", str(user.id))

    return jsonify({
        "access_token":  _make_access_token(user),
        "refresh_token": create_refresh_token(identity=str(user.id)),
        "user":    user.to_dict(),
        "company": user.company.to_dict(),
    })


# ── Refresh ───────────────────────────────────────────────────────────────────

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    user = User.query.get(int(get_jwt_identity()))
    if not user or not user.is_active:
        return jsonify({"error": "Utilisateur invalide"}), 401
    return jsonify({"access_token": _make_access_token(user)})


# ── Logout ────────────────────────────────────────────────────────────────────

@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]
    block_token(jti)
    log_action(current_company_id(), current_user_id(), "LOGOUT", "user")
    return jsonify({"message": "Déconnexion réussie"})


# ── Profile ───────────────────────────────────────────────────────────────────

@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user = User.query.get(current_user_id())
    if not user:
        return jsonify({"error": "Utilisateur introuvable"}), 404
    return jsonify({"user": user.to_dict(), "company": user.company.to_dict()})


@auth_bp.route("/me", methods=["PUT"])
@jwt_required()
def update_profile():
    """Modifier les informations personnelles du compte connecté.

    Le mot de passe n'est pas modifié ici. Il possède une route séparée
    qui exige le mot de passe actuel pour éviter les changements non sécurisés.
    """
    user = User.query.get(current_user_id())
    if not user:
        return jsonify({"error": "Utilisateur introuvable"}), 404

    data = request.get_json(force=True) or {}

    for field in ["nom", "prenom"]:
        if field in data:
            setattr(user, field, (data[field] or "").strip())

    db.session.commit()
    log_action(user.company_id, user.id, "UPDATE_PROFILE", "user", str(user.id))
    return jsonify({"message": "Profil mis à jour", "user": user.to_dict()})


@auth_bp.route("/me/password", methods=["PUT"])
@jwt_required()
def update_own_password():
    """Modifier le mot de passe du compte connecté.

    Accessible à l'administrateur et à l'agent financier. L'utilisateur doit
    saisir son mot de passe actuel puis confirmer un nouveau mot de passe.
    """
    user = User.query.get(current_user_id())
    if not user:
        return jsonify({"error": "Utilisateur introuvable"}), 404

    data = request.get_json(force=True) or {}
    current_password = data.get("current_password") or data.get("old_password") or ""
    new_password = data.get("new_password") or data.get("password") or ""
    confirm_password = data.get("confirm_password") or data.get("confirm") or new_password

    if not current_password or not new_password:
        return jsonify({"error": "Mot de passe actuel et nouveau mot de passe requis"}), 400

    if not bcrypt.check_password_hash(user.password_hash, current_password):
        return jsonify({"error": "Mot de passe actuel incorrect"}), 401

    if new_password != confirm_password:
        return jsonify({"error": "Les mots de passe ne correspondent pas"}), 400

    if current_password == new_password:
        return jsonify({"error": "Le nouveau mot de passe doit être différent de l'ancien"}), 400

    issues = validate_password_strength(new_password)
    if issues:
        return jsonify({"error": issues[0]}), 400

    user.password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
    db.session.commit()
    log_action(user.company_id, user.id, "CHANGE_PASSWORD", "user", str(user.id))

    return jsonify({"message": "Mot de passe modifié avec succès"})


# ── User management (admin) ───────────────────────────────────────────────────

@auth_bp.route("/users", methods=["GET"])
@jwt_required()
@admin_required
def list_users():
    users = User.query.filter_by(company_id=current_company_id()).all()
    return jsonify({"users": [u.to_dict() for u in users]})


@auth_bp.route("/users", methods=["POST"])
@jwt_required()
@admin_required
def create_user():
    data = request.get_json(force=True) or {}
    required = ["email", "password", "role"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Champs requis: {missing}"}), 400

    if User.query.filter_by(
        company_id=current_company_id(), email=data["email"].lower()
    ).first():
        return jsonify({"error": "Email déjà utilisé dans cette société"}), 409

    nom_complet = data.get("nom_complet") or data.get("fullName") or ""
    prenom = data.get("prenom", "")
    nom = data.get("nom", "")
    if nom_complet and not (prenom or nom):
        parts = nom_complet.strip().split(" ", 1)
        prenom = parts[0] if len(parts) > 0 else ""
        nom = parts[1] if len(parts) > 1 else ""

    user = User(
        company_id=current_company_id(),
        email=data["email"].lower(),
        password_hash=bcrypt.generate_password_hash(data["password"]).decode(),
        nom=nom,
        prenom=prenom,
        role=data.get("role", "USER"),
    )
    db.session.add(user)
    db.session.commit()
    log_action(current_company_id(), current_user_id(), "CREATE_USER", "user", str(user.id))
    return jsonify({"user": user.to_dict()}), 201


@auth_bp.route("/users/<int:uid>", methods=["PUT"])
@jwt_required()
@admin_required
def update_user(uid: int):
    user = User.query.filter_by(id=uid, company_id=current_company_id()).first_or_404()
    data = request.get_json(force=True) or {}
    for field in ["nom", "prenom", "role", "is_active"]:
        if field in data:
            setattr(user, field, data[field])
    if "password" in data and data["password"]:
        user.password_hash = bcrypt.generate_password_hash(data["password"]).decode()
    db.session.commit()
    log_action(current_company_id(), current_user_id(), "UPDATE_USER", "user", str(user.id))
    return jsonify({"user": user.to_dict()})


@auth_bp.route("/users/<int:uid>", methods=["DELETE"])
@jwt_required()
@admin_required
def delete_user(uid: int):
    """Supprimer un utilisateur (cas d'utilisation: Gérer les utilisateurs)."""
    cid = current_company_id()
    # Empêcher l'admin de se supprimer lui-même
    if uid == current_user_id():
        return jsonify({"error": "Vous ne pouvez pas supprimer votre propre compte"}), 400
    user = User.query.filter_by(id=uid, company_id=cid).first_or_404()
    db.session.delete(user)
    db.session.commit()
    log_action(cid, current_user_id(), "DELETE_USER", "user", str(uid))
    return jsonify({"message": "Utilisateur supprimé avec succès"})


# ── Helper ────────────────────────────────────────────────────────────────────

def _make_access_token(user: User) -> str:
    return create_access_token(
        identity=str(user.id),
        additional_claims={
            "company_id": user.company_id,
            "role": user.role,
            "email": user.email,
        },
    )

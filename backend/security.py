"""
security.py
JWT helpers, permission decorators, and password utilities.
"""
from __future__ import annotations

from functools import wraps
from typing import Callable

from flask import jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request


# ── Identity helpers ──────────────────────────────────────────────────────────

def current_user_id() -> int:
    """Return the user_id embedded in the JWT."""
    return int(get_jwt_identity())


def current_company_id() -> int:
    """Return the company_id from the JWT claims."""
    return int(get_jwt().get("company_id", 0))


def current_role() -> str:
    return get_jwt().get("role", "USER")


# ── Role decorators ───────────────────────────────────────────────────────────

def roles_required(*roles: str) -> Callable:
    """Decorator: allow only users with one of the specified roles."""
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            role = current_role()
            if role not in roles:
                return jsonify({"error": f"Rôle '{role}' insuffisant. Requis: {list(roles)}"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def admin_required(fn: Callable) -> Callable:
    return roles_required("ADMIN")(fn)


def manager_or_admin(fn: Callable) -> Callable:
    # Kept for backward compatibility with older routes. New sensitive actions
    # in this PFE version use admin_required because the Responsable Financier
    # / agent is read-only according to the conception.
    return roles_required("ADMIN", "MANAGER")(fn)


def agent_or_admin(fn: Callable) -> Callable:
    """Allow read-only consultation roles and administrators.

    Role aliases are accepted because older local databases/frontends may store
    the financial agent as MANAGER, AGENT, FINANCE, FINANCIER, or
    RESPONSABLE_FINANCIER.
    """
    return roles_required(
        "ADMIN", "MANAGER", "AGENT", "FINANCE", "FINANCIER", "RESPONSABLE_FINANCIER"
    )(fn)


# ── Password utilities ────────────────────────────────────────────────────────

def validate_password_strength(password: str) -> list[str]:
    """Return list of weakness messages; empty list = valid."""
    errors = []
    if len(password) < 8:
        errors.append("Le mot de passe doit contenir au moins 8 caractères.")
    if not any(c.isupper() for c in password):
        errors.append("Au moins une lettre majuscule requise.")
    if not any(c.isdigit() for c in password):
        errors.append("Au moins un chiffre requis.")
    return errors


# ── Token blocklist (in-memory for dev; use Redis in production) ──────────────

_BLOCKLIST: set[str] = set()


def block_token(jti: str) -> None:
    _BLOCKLIST.add(jti)


def is_token_blocked(jti: str) -> bool:
    return jti in _BLOCKLIST

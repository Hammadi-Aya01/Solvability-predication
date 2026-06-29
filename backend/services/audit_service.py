"""
services/audit_service.py
Audit log helper — called from routes after every mutation.
"""
from __future__ import annotations

from flask import request as flask_request

from extensions import db
from models import AuditLog


def log_action(
    company_id: int,
    user_id: int,
    action: str,
    resource: str = "",
    resource_id: str = "",
    detail: dict | None = None,
) -> None:
    """Persist an audit log entry. Non-blocking — errors are swallowed."""
    try:
        entry = AuditLog(
            company_id=company_id,
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=str(resource_id) if resource_id else "",
            detail=detail or {},
            ip_address=_get_ip(),
            user_agent=(
                flask_request.headers.get("User-Agent", "")[:256]
                if flask_request else ""
            ),
        )
        db.session.add(entry)
        db.session.flush()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"audit_log_failed: {e}")


def _get_ip() -> str:
    try:
        return (
            flask_request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or flask_request.remote_addr
            or ""
        )
    except Exception:
        return ""

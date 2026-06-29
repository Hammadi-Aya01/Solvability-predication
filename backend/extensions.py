"""
extensions.py
Shared Flask extension instances (initialised in app factory).
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_bcrypt import Bcrypt

db      = SQLAlchemy()
migrate = Migrate()
jwt     = JWTManager()
cache   = Cache()
bcrypt  = Bcrypt()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per hour"],
    storage_uri="memory://",   # overridden by app config
)

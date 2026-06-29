"""
config.py
Environment-based configuration for SolvAI.
"""
from __future__ import annotations

import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))



class BaseConfig:
    # ── Core ──────────────────────────────────────────────────────────────
    SECRET_KEY         = os.getenv("SECRET_KEY", "change-me-in-production-please")
    REGISTRATION_SECRET = os.getenv("REGISTRATION_SECRET", "super-secret-tech-key")
    DEBUG              = False
    TESTING            = False

    # ── Database ──────────────────────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql://solvai:solvai@localhost:5432/solvai_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size":         10,
        "pool_recycle":      3600,
        "pool_pre_ping":     True,
        "max_overflow":      20,
    }

    # ── JWT ───────────────────────────────────────────────────────────────
    JWT_SECRET_KEY            = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES  = timedelta(hours=int(os.getenv("JWT_EXPIRE_HOURS", 8)))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_ALGORITHM             = "HS256"

    # ── Redis / Celery ────────────────────────────────────────────────────
    REDIS_URL             = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL     = os.getenv("CELERY_BROKER_URL",  REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

    # ── Cache ─────────────────────────────────────────────────────────────
    CACHE_TYPE            = "RedisCache"
    CACHE_REDIS_URL       = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = 300

    # ── Rate limiting ─────────────────────────────────────────────────────
    RATELIMIT_STORAGE_URL   = REDIS_URL
    RATELIMIT_DEFAULT       = "200 per hour"
    RATELIMIT_STRATEGY      = "fixed-window"

    # ── File uploads ──────────────────────────────────────────────────────
    UPLOAD_FOLDER     = os.getenv("UPLOAD_FOLDER",  os.path.join(BASE_DIR, "uploads"))
    EXPORT_FOLDER     = os.getenv("EXPORT_FOLDER",  os.path.join(BASE_DIR, "exports"))
    MODEL_DIR         = os.getenv("MODEL_DIR",       os.path.join(BASE_DIR, "trained_models"))
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024   # 50 MB
    ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}

    # ── CORS ──────────────────────────────────────────────────────────────
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

    # ── ML training ───────────────────────────────────────────────────────
    OPTUNA_TRIALS      = int(os.getenv("OPTUNA_TRIALS", 20))
    ML_TASK_TIMEOUT    = int(os.getenv("ML_TASK_TIMEOUT", 3600))   # seconds

    # ── Security ──────────────────────────────────────────────────────────
    BCRYPT_LOG_ROUNDS = int(os.getenv("BCRYPT_LOG_ROUNDS", 12))
    PASSWORD_MIN_LEN  = 8

    # ── Pagination ────────────────────────────────────────────────────────
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE     = 100


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql://solvai:solvai@localhost:5432/solvai_dev"
    )
    CACHE_TYPE            = "SimpleCache"
    RATELIMIT_STORAGE_URL = "memory://"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)

    @property
    def _is_sqlite(self):
        uri = os.getenv("DATABASE_URL", "")
        return uri.lower().startswith("sqlite")

    # FIX: SQLite does not support pool_size/pool_recycle/max_overflow.
    # Override engine options to NullPool when SQLite is detected.
    SQLALCHEMY_ENGINE_OPTIONS = (
        {"poolclass": __import__("sqlalchemy.pool", fromlist=["NullPool"]).NullPool}
        if os.getenv("DATABASE_URL", "").lower().startswith("sqlite")
        else BaseConfig.SQLALCHEMY_ENGINE_OPTIONS
    )


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG   = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    CACHE_TYPE              = "SimpleCache"
    RATELIMIT_ENABLED       = False
    WTF_CSRF_ENABLED        = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)


class ProductionConfig(BaseConfig):
    DEBUG   = False
    TESTING = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        **BaseConfig.SQLALCHEMY_ENGINE_OPTIONS,
        "pool_size": 20,
        "max_overflow": 40,
    }
    BCRYPT_LOG_ROUNDS = 14


_CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing":     TestingConfig,
    "production":  ProductionConfig,
}


def get_config(env: str = "development"):
    return _CONFIG_MAP.get(env, DevelopmentConfig)

"""Application configuration."""
import os
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from dotenv import load_dotenv

load_dotenv()


def _redis_url(value: str | None) -> str | None:
    """Require certificate verification for TLS Redis connections."""
    if not value or not value.startswith("rediss://"):
        return value
    parts = urlsplit(value)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("ssl_cert_reqs", "CERT_REQUIRED")
    return urlunsplit(parts._replace(query=urlencode(query)))


def _postgresql_url(value: str | None) -> str | None:
    """Use the installed Psycopg 3 driver for Postgres URLs."""
    if not value:
        return value
    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://"):]
    if value.startswith("postgresql://"):
        value = "postgresql+psycopg://" + value[len("postgresql://"):]
    return value


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "30")))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "30")))
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 10,
        "max_overflow": 20,
    }

    # Celery
    CELERY_BROKER_URL = _redis_url(os.getenv("CELERY_BROKER_URL", "memory://"))
    CELERY_RESULT_BACKEND = _redis_url(os.getenv("CELERY_RESULT_BACKEND", "cache+memory://"))

    # CORS
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")

    # Uploads
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "/tmp/pika_uploads")
    AWS_ENDPOINT_URL_S3 = os.getenv("AWS_ENDPOINT_URL_S3")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = os.getenv("AWS_REGION")
    AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")
    USE_OBJECT_STORAGE = all((AWS_ENDPOINT_URL_S3, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, AWS_BUCKET_NAME))
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "txt", "doc", "docx", "csv", "xlsx"}

    # Email
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USERNAME or "")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    # Rate limiting
    RATELIMIT_STORAGE_URI = _redis_url(os.getenv("RATELIMIT_STORAGE_URI", "memory://"))

    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    # Security
    BCRYPT_LOG_ROUNDS = 12
    PASSWORD_MIN_LENGTH = 8


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = _postgresql_url(os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/pika_dev"
    ))
    CELERY_BROKER_URL = _redis_url(os.getenv("CELERY_BROKER_URL", "memory://"))
    CELERY_RESULT_BACKEND = _redis_url(os.getenv("CELERY_RESULT_BACKEND", "cache+memory://"))
    RATELIMIT_STORAGE_URI = "memory://"


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = _postgresql_url(os.getenv("DATABASE_URL"))

    CELERY_BROKER_URL = _redis_url(os.getenv("CELERY_BROKER_URL"))  # Upstash Redis
    CELERY_RESULT_BACKEND = _redis_url(os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL))
    RATELIMIT_STORAGE_URI = _redis_url(os.getenv("RATELIMIT_STORAGE_URI", CELERY_BROKER_URL))

    # Stricter in prod
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    BCRYPT_LOG_ROUNDS = 13


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = _postgresql_url(os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/pika_test"
    ))
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"
    RATELIMIT_STORAGE_URI = "memory://"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    WTF_CSRF_ENABLED = False

"""Pika Helpdesk Platform - Application Factory"""
import os
import ssl
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from celery import Celery
import structlog

from app.config import Config, DevelopmentConfig, ProductionConfig, TestingConfig

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])
celery = Celery(__name__)

logger = structlog.get_logger()


def create_app(config_name: str = None) -> Flask:
    """Application factory."""
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)

    config_map = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestingConfig,
    }
    app.config.from_object(config_map.get(config_name, DevelopmentConfig))

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)

    # CORS
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": app.config.get("CORS_ORIGINS", ["http://localhost:5173"]),
                "supports_credentials": True,
                "allow_headers": ["Content-Type", "Authorization", "X-Idempotency-Key"],
                "expose_headers": ["X-Total-Count", "X-Page", "X-Per-Page"],
            }
        },
    )

    # Celery
    celery.conf.update(
        broker_url=app.config["CELERY_BROKER_URL"],
        result_backend=app.config["CELERY_RESULT_BACKEND"],
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_soft_time_limit=300,
        task_time_limit=600,
        broker_connection_retry_on_startup=True,
    )
    celery.conf.update(app.config)
    if str(app.config["CELERY_BROKER_URL"]).startswith("rediss://"):
        celery.conf.update(
            broker_use_ssl={"ssl_cert_reqs": ssl.CERT_REQUIRED},
        )
    if str(app.config["CELERY_RESULT_BACKEND"]).startswith("rediss://"):
        celery.conf.update(
            redis_backend_use_ssl={"ssl_cert_reqs": ssl.CERT_REQUIRED},
        )

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    # Register blueprints
    from app.api.v1 import api_v1_bp
    app.register_blueprint(api_v1_bp, url_prefix="/api/v1")

    # Health checks
    @app.route("/health")
    def health():
        return {"status": "ok", "service": "pika-api"}, 200

    @app.route("/ready")
    def ready():
        try:
            db.session.execute(db.text("SELECT 1"))
            return {"status": "ready"}, 200
        except Exception as e:
            logger.error("readiness_check_failed", error=str(e))
            return {"status": "not_ready", "error": str(e)}, 503

    # Error handlers
    from app.utils.errors import register_error_handlers
    register_error_handlers(app)

    # JWT callbacks
    from app.utils.jwt_handlers import register_jwt_handlers
    register_jwt_handlers(jwt)

    # Structured logging
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return app

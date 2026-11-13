"""Centralized error handling and custom exceptions."""
from flask import jsonify
from werkzeug.exceptions import HTTPException
import structlog

logger = structlog.get_logger()


class AppError(Exception):
    """Base application error."""
    status_code = 400
    error_code = "app_error"

    def __init__(self, message: str, status_code: int = None, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code
        self.details = details or {}


class ValidationError(AppError):
    status_code = 422
    error_code = "validation_error"


class AuthenticationError(AppError):
    status_code = 401
    error_code = "authentication_error"


class AuthorizationError(AppError):
    status_code = 403
    error_code = "authorization_error"


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"


class ConflictError(AppError):
    status_code = 409
    error_code = "conflict"


class RateLimitError(AppError):
    status_code = 429
    error_code = "rate_limit_exceeded"


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(e: AppError):
        logger.warning("app_error", error_code=e.error_code, message=e.message, details=e.details)
        response = {
            "error": {
                "code": e.error_code,
                "message": e.message,
            }
        }
        if e.details:
            response["error"]["details"] = e.details
        return jsonify(response), e.status_code

    @app.errorhandler(HTTPException)
    def handle_http_exception(e: HTTPException):
        return jsonify({
            "error": {
                "code": e.name.lower().replace(" ", "_"),
                "message": e.description,
            }
        }), e.code

    @app.errorhandler(Exception)
    def handle_unexpected(e: Exception):
        logger.exception("unexpected_error", error=str(e))
        return jsonify({
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred.",
            }
        }), 500

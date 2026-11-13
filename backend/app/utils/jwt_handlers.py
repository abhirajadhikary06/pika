"""JWT callbacks and helpers."""
from flask import jsonify
from flask_jwt_extended import get_jwt
from datetime import datetime, timezone
from app import db
from app.models.token import RefreshToken
import structlog

logger = structlog.get_logger()


def register_jwt_handlers(jwt):
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({
            "error": {
                "code": "token_expired",
                "message": "The token has expired.",
            }
        }), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error_string):
        return jsonify({
            "error": {
                "code": "invalid_token",
                "message": "Invalid token.",
            }
        }), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error_string):
        return jsonify({
            "error": {
                "code": "authorization_required",
                "message": "Authorization header is missing or invalid.",
            }
        }), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({
            "error": {
                "code": "token_revoked",
                "message": "The token has been revoked.",
            }
        }), 401

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        jti = jwt_payload.get("jti")
        token_type = jwt_payload.get("type")
        if token_type != "refresh":
            return False
        token = RefreshToken.query.filter_by(jti=jti).first()
        if token is None:
            return True  # unknown refresh token treated as revoked
        return token.is_revoked or token.is_expired

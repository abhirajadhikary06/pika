"""Authentication endpoints."""
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from flask import request, g
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    get_jwt,
    jwt_required,
)
from app import db, limiter
from app.api.v1 import api_v1_bp
from app.models.user import User
from app.models.token import RefreshToken
from app.utils.auth import require_auth
from app.utils.errors import ValidationError, AuthenticationError, ConflictError
from app.utils.validators import require_fields, validate_email, validate_password, success_response
import structlog

logger = structlog.get_logger()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@api_v1_bp.route("/auth/register", methods=["POST"])
@limiter.limit("10 per hour")
def register():
    data = request.get_json(silent=True) or {}
    require_fields(data, ["email", "password", "full_name"])

    email = validate_email(data["email"])
    password = validate_password(data["password"])
    full_name = data["full_name"].strip()
    if len(full_name) < 2 or len(full_name) > 150:
        raise ValidationError("Full name must be 2-150 characters.")

    if User.query.filter_by(email=email).first():
        raise ConflictError("An account with this email already exists.")

    user = User(email=email, full_name=full_name)
    user.set_password(password)
    user.is_verified = True  # skip email verification for now
    db.session.add(user)
    db.session.commit()

    logger.info("user_registered", user_id=str(user.id), email=email)
    return success_response(user.to_dict(), message="Registration successful.", status=201)


@api_v1_bp.route("/auth/login", methods=["POST"])
@limiter.limit("20 per hour")
def login():
    data = request.get_json(silent=True) or {}
    require_fields(data, ["email", "password"])

    email = validate_email(data["email"])
    password = data["password"]

    user = User.query.filter_by(email=email).first()
    if not user:
        raise AuthenticationError("Email address not found.")
    if not user.check_password(password):
        raise AuthenticationError("Password is incorrect.")
    if not user.is_active:
        raise AuthenticationError("Account is deactivated.")

    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()

    access_token = create_access_token(identity=str(user.id), additional_claims={"type": "access"})
    refresh_token = create_refresh_token(identity=str(user.id), additional_claims={"type": "refresh"})

    # Persist refresh token for revocation
    jwt_data = get_jwt() if False else {}  # we need jti from the created token
    # Create token object manually
    from flask_jwt_extended import decode_token
    decoded = decode_token(refresh_token)
    jti = decoded["jti"]
    expires = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)

    rt = RefreshToken(
        user_id=user.id,
        jti=jti,
        token_hash=_hash_token(refresh_token),
        expires_at=expires,
        user_agent=request.headers.get("User-Agent", "")[:300],
        ip_address=request.remote_addr,
    )
    db.session.add(rt)
    db.session.commit()

    logger.info("user_login", user_id=str(user.id))
    return success_response({
        "user": user.to_dict(),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": 30 * 60,
    })


@api_v1_bp.route("/auth/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    claims = get_jwt()
    jti = claims.get("jti")

    token_rec = RefreshToken.query.filter_by(jti=jti).first()
    if not token_rec or token_rec.is_revoked or token_rec.is_expired:
        raise AuthenticationError("Refresh token is invalid or revoked.")

    user = User.query.get(identity)
    if not user or not user.is_active:
        raise AuthenticationError("User not found or inactive.")

    access_token = create_access_token(identity=str(user.id), additional_claims={"type": "access"})
    return success_response({
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 30 * 60,
    })


@api_v1_bp.route("/auth/logout", methods=["POST"])
@jwt_required(refresh=True)
def logout():
    claims = get_jwt()
    jti = claims.get("jti")
    token_rec = RefreshToken.query.filter_by(jti=jti).first()
    if token_rec and not token_rec.is_revoked:
        token_rec.revoke()
        db.session.commit()
    return success_response(message="Logged out successfully.")


@api_v1_bp.route("/auth/me", methods=["GET"])
@require_auth
def me():
    return success_response(g.current_user.to_dict())


@api_v1_bp.route("/auth/me", methods=["PATCH"])
@require_auth
def update_me():
    data = request.get_json(silent=True) or {}
    user = g.current_user

    if "full_name" in data:
        name = data["full_name"].strip()
        if len(name) < 2 or len(name) > 150:
            raise ValidationError("Full name must be 2-150 characters.")
        user.full_name = name
        user.version += 1

    if "avatar_url" in data:
        user.avatar_url = data["avatar_url"]
        user.version += 1

    if "password" in data:
        require_fields(data, ["current_password"])
        if not user.check_password(data["current_password"]):
            raise AuthenticationError("Current password is incorrect.")
        new_pw = validate_password(data["password"])
        user.set_password(new_pw)
        user.version += 1

    db.session.commit()
    return success_response(user.to_dict(), message="Profile updated.")

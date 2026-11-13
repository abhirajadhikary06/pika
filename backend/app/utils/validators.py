"""Request validation helpers using simple dict schemas (no heavy marshmallow dependency for core)."""
import re
from typing import Any
from app.utils.errors import ValidationError


EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def require_fields(data: dict, fields: list[str]) -> None:
    missing = [f for f in fields if f not in data or data[f] is None or (isinstance(data[f], str) and not data[f].strip())]
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}", details={"fields": missing})


def validate_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise ValidationError("Invalid email address.")
    return email


def validate_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValidationError("Password must be at least 8 characters.")
    if len(password) > 128:
        raise ValidationError("Password is too long.")
    return password


def validate_slug(slug: str) -> str:
    slug = (slug or "").strip().lower()
    if not SLUG_RE.match(slug) or len(slug) < 2 or len(slug) > 100:
        raise ValidationError("Slug must be 2-100 chars, lowercase alphanumeric with hyphens.")
    return slug


def paginate_params(args) -> tuple[int, int]:
    try:
        page = max(1, int(args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = min(100, max(1, int(args.get("per_page", 20))))
    except (TypeError, ValueError):
        per_page = 20
    return page, per_page


def success_response(data: Any = None, message: str = None, meta: dict = None, status: int = 200):
    body = {}
    if message:
        body["message"] = message
    if data is not None:
        body["data"] = data
    if meta:
        body["meta"] = meta
    from flask import jsonify
    return jsonify(body), status

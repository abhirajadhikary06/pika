"""API v1 blueprints."""
from flask import Blueprint

api_v1_bp = Blueprint("api_v1", __name__)

from app.api.v1 import auth, workspaces, tickets, users, notifications  # noqa: E402, F401

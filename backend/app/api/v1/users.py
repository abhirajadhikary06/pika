"""User related endpoints (mostly profile already in auth)."""
from app.api.v1 import api_v1_bp
from app.utils.auth import require_auth
from app.utils.validators import success_response
from flask import g


@api_v1_bp.route("/users/me", methods=["GET"])
@require_auth
def current_user_profile():
    return success_response(g.current_user.to_dict())

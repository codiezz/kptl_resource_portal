from functools import wraps

from flask import jsonify, session


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return jsonify({"error": "Not authenticated"}), 401
        return view(*args, **kwargs)

    return wrapped


def role_required(*allowed_roles):
    """
    Restrict a route to one or more roles.

    Usage:
        @role_required("ADMIN")
        @role_required("ADMIN", "USER")

    Behavior:
        - No active session -> 401 JSON (not authenticated at all)
        - Session exists but role not in allowed_roles -> 403 JSON
        - Never redirects, never returns HTML — always a JSON error body,
          per the project's authorization architecture.
    """
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user" not in session:
                return jsonify({"error": "Not authenticated"}), 401

            if session.get("role") not in allowed_roles:
                return jsonify({
                    "error": "You do not have permission to access this resource"
                }), 403

            return view(*args, **kwargs)

        return wrapped

    return decorator
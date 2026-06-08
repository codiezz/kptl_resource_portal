from flask import Blueprint, jsonify, request, session

import config

auth_bp = Blueprint("auth", __name__, url_prefix="/api")


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json or {}

    username = data.get("username")
    password = data.get("password")

    user = config.USERS.get(username)

    if user and user["password"] == password:
        session["user"] = username
        session["role"] = user["role"]

        return jsonify({
            "username": username,
            "role": user["role"],
        })

    return jsonify({"error": "Invalid credentials"}), 401


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"}), 200


@auth_bp.route("/auth-check")
def auth_check():
    if "user" in session:
        return jsonify({
            "authenticated": True,
            "username": session["user"],
            "role": session["role"],
        })

    return jsonify({"authenticated": False})

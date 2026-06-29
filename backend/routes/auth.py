from flask import Blueprint, jsonify, request, session

import pymysql

import config
import models

auth_bp = Blueprint("auth", __name__, url_prefix="/api")
MIN_PASSWORD_LENGTH = 6

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.json or {}

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    # --- Validation ---
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if not email.endswith(config.ALLOWED_EMAIL_DOMAIN):
        return jsonify({
            "error": f"Only {config.ALLOWED_EMAIL_DOMAIN} email addresses are allowed"
        }), 400

    if len(password) < MIN_PASSWORD_LENGTH:
        return jsonify({
            "error": f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
        }), 400

    # --- Create user (always as USER — registration can never create an ADMIN) ---
    try:
        user_id = models.create_user(email, password, role="USER")
    except pymysql.err.IntegrityError:
        return jsonify({"error": "An account with this email already exists"}), 409

    # --- Auto-login: create the session immediately, same shape as /login ---
    session["user"] = email
    session["role"] = "USER"

    return jsonify({
        "username": email,
        "role": "USER",
    }), 201

    
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

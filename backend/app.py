from flask import Flask, request, jsonify, session
from flask_cors import CORS
import os
import sys
sys.path.insert(0, 'ssh_layer')
from ssh_executor import run_hpc_command, SSHError, SSHAuthError, SSHTimeoutError
from slurm_parser import parse_cluster_utilization

app = Flask(__name__)

# Secret key for session encryption — change this in production
app.secret_key = "hpc-portal-secret-key-change-in-prod"

# Session config
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True

# Allow CORS from the React dev server, with credentials (cookies)
CORS(app, supports_credentials=True, origins=["http://localhost:5173"])

# ---------------------------------------------------------------------------
# Hardcoded users — replace with a database when ready
# ---------------------------------------------------------------------------
users = {
    "admin": {
        "password": "admin123",
        "role": "admin",
    },

    "test": {
        "password": "test123",
        "role": "user",
    },
}


# ---------------------------------------------------------------------------
# POST /api/login
# Body: { "username": "...", "password": "..." }
# ---------------------------------------------------------------------------
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json

    username = data.get("username")
    password = data.get("password")

    user = users.get(username)

    if (
        user
        and user["password"] == password
    ):
        session["user"] = username
        session["role"] = user["role"]

        return jsonify({
            "username": username,
            "role": user["role"],
        })

    return jsonify({
        "error":
        "Invalid credentials"
    }), 401

# ---------------------------------------------------------------------------
# POST /api/logout
# ---------------------------------------------------------------------------
@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"}), 200


# ---------------------------------------------------------------------------
# GET /api/auth-check
# Returns the logged-in user or 401 if not authenticated
# ---------------------------------------------------------------------------
@app.route("/api/auth-check")
def auth_check():

    if "user" in session:
        return jsonify({
            "authenticated": True,
            "username":
                session["user"],
            "role":
                session["role"],
        })

    return jsonify({
        "authenticated": False
    })

# ---------------------------------------------------------------------------
# POST /api/clusters/<cluster_id>/health
# Runs sreport utilization on the target cluster
# ---------------------------------------------------------------------------

# Temporary hardcoded cluster config — move to DB later
CLUSTERS = {
    "fortytwo": {
        "host": "192.168.1.152",  # <-- replace this
        "port": 22,
    }
}

@app.route("/api/clusters/<cluster_id>/health", methods=["POST"])
def get_cluster_health(cluster_id):
    if "user" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    cluster = CLUSTERS.get(cluster_id)
    if not cluster:
        return jsonify({"error": f"Unknown cluster: {cluster_id}"}), 404

    body = request.get_json(silent=True) or {}
    start = body.get("start", "2025-10-01")
    end   = body.get("end",   "2025-12-31")

    # Temporary hardcoded credentials — move to encrypted DB later
    username = os.environ.get("HPC_USER", "")
    password = os.environ.get("HPC_PASS", "")

    if not username or not password:
        return jsonify({"error": "HPC credentials not set"}), 500

    command = f"sreport cluster Utilization start={start} end={end} -t percent"

    try:
        raw = run_hpc_command(
            host=cluster["host"],
            username=username,
            password=password,
            command=command,
            port=cluster["port"],
            timeout=30,
        )
    except SSHAuthError as e:
        return jsonify({"error": "Authentication failed", "detail": str(e)}), 401
    except SSHTimeoutError:
        return jsonify({"error": "Cluster connection timed out"}), 504
    except SSHError as e:
        return jsonify({"error": "SSH failed", "detail": str(e)}), 502

    parsed = parse_cluster_utilization(raw)

    if not parsed.get("metrics"):
        return jsonify({"error": "Could not parse output", "raw": raw}), 500

    parsed.pop("raw", None)
    return jsonify(parsed), 200
if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5000)

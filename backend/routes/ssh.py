import os
import sys

from flask import Blueprint, jsonify, request

import config
from auth import login_required

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ssh_layer"))
from login_session_store import cleanup_expired, pop, store
from ssh_executor import (
    SSHAuthError,
    SSHCommandError,
    SSHConnectionError,
    SSHError,
    SSHExecutor,
    SSHTimeoutError,
)

ssh_bp = Blueprint("ssh", __name__, url_prefix="/api/ssh")


def _resolve_cluster(body):
    cluster_id = body.get("cluster_id")
    if cluster_id:
        cluster = config.CLUSTERS.get(cluster_id)
        if not cluster:
            return None, jsonify({"error": f"Unknown cluster: {cluster_id}"}), 404
        return cluster, None, None

    host = body.get("host")
    if not host:
        return None, jsonify({"error": "cluster_id or host is required"}), 400

    return {
        "host": host,
        "port": body.get("port", 22),
    }, None, None


def _hpc_username():
    return os.environ.get("HPC_USER", "")


def _hpc_password():
    return os.environ.get("HPC_PASS", "")


@ssh_bp.route("/login/start", methods=["POST"])
@login_required
def ssh_login_start():
    """
    Step 1: username auto-fill, pause at captcha for manual entry.

    Returns session_id + challenge_text. Password is not used yet.
    """
    cleanup_expired()

    body = request.get_json(silent=True) or {}
    cluster, error_response, status = _resolve_cluster(body)
    if error_response is not None:
        return error_response, status

    username = _hpc_username()
    if not username:
        return jsonify({"error": "HPC username not configured (HPC_USER)"}), 500

    executor = SSHExecutor(
        host=cluster["host"],
        port=cluster.get("port", 22),
        timeout=body.get("timeout", 30),
    )

    try:
        pending = executor.begin_login(username)
    except SSHConnectionError as exc:
        return jsonify({"error": "Connection failed", "detail": str(exc)}), 502
    except SSHTimeoutError:
        return jsonify({"error": "Connection timed out"}), 504
    except SSHError as exc:
        return jsonify({"error": "SSH login start failed", "detail": str(exc)}), 502

    session_id = store(pending)

    return jsonify({
        "session_id": session_id,
        "username": username,
        "stage": pending.stage,
        "captcha_required": pending.stage == "captcha",
        "challenge_text": pending.challenge_text,
    }), 200


@ssh_bp.route("/login/complete", methods=["POST"])
@login_required
def ssh_login_complete():
    """
    Step 2: user-supplied captcha + password auto-fill from HPC_PASS.

    Completes the pending pexpect session started by /login/start.
    """
    body = request.get_json(silent=True) or {}
    session_id = body.get("session_id")
    captcha_answer = body.get("captcha_answer")

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    pending = pop(session_id)
    if pending is None:
        return jsonify({"error": "Invalid or expired SSH login session"}), 404

    password = _hpc_password()
    if not password:
        pending.close()
        return jsonify({"error": "HPC password not configured (HPC_PASS)"}), 500

    command = body.get("command", "echo connected")

    try:
        result = pending.complete(
            password=password,
            captcha_answer=captcha_answer,
            command=command,
        )
    except SSHAuthError as exc:
        return jsonify({"error": "Authentication failed", "detail": str(exc)}), 401
    except SSHCommandError as exc:
        return jsonify({"error": "Command failed", "detail": str(exc)}), 502
    except SSHTimeoutError:
        return jsonify({"error": "SSH operation timed out"}), 504
    except SSHError as exc:
        return jsonify({"error": "SSH failed", "detail": str(exc)}), 502

    return jsonify({
        "connected": True,
        "username": pending.username,
        "host": result.host,
        "command": result.command,
        "output": result.stdout,
    }), 200

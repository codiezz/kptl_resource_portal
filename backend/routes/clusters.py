import os
import sys

from flask import Blueprint, jsonify, request

import config
from auth import login_required

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ssh_layer"))
from slurm_parser import parse_cluster_utilization
from ssh_executor import SSHAuthError, SSHError, SSHTimeoutError, run_hpc_command

clusters_bp = Blueprint("clusters", __name__, url_prefix="/api/clusters")


@clusters_bp.route("", methods=["GET"])
@login_required
def list_clusters():
    """Return cluster ids and display names (no host details)."""
    clusters = [
        {
            "id": cluster_id,
            "display_name": meta.get("display_name", cluster_id),
        }
        for cluster_id, meta in config.CLUSTERS.items()
    ]
    return jsonify({"clusters": clusters}), 200


@clusters_bp.route("/<cluster_id>/health", methods=["POST"])
@login_required
def get_cluster_health(cluster_id):
    cluster = config.CLUSTERS.get(cluster_id)
    if not cluster:
        return jsonify({"error": f"Unknown cluster: {cluster_id}"}), 404

    body = request.get_json(silent=True) or {}
    start = body.get("start", config.DEFAULT_UTILIZATION_START)
    end = body.get("end", config.DEFAULT_UTILIZATION_END)

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
    except SSHAuthError as exc:
        return jsonify({"error": "Authentication failed", "detail": str(exc)}), 401
    except SSHTimeoutError:
        return jsonify({"error": "Cluster connection timed out"}), 504
    except SSHError as exc:
        return jsonify({"error": "SSH failed", "detail": str(exc)}), 502

    parsed = parse_cluster_utilization(raw)

    if not parsed.get("metrics"):
        return jsonify({"error": "Could not parse output", "raw": raw}), 500

    parsed.pop("raw", None)
    return jsonify(parsed), 200

from flask import Flask, request, jsonify, session, send_file
from flask_cors import CORS
import os
import io
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ssh_layer'))
from pdf_generator import generate_utilization_report
from ssh_layer.ssh_executor import (
    run_hpc_command,
    SSHError,
    SSHAuthError,
    SSHTimeoutError,
)
from ssh_layer.slurm_parser import parse_cluster_utilization

import config
from routes import auth_bp, clusters_bp, ssh_bp


def create_app():
    app = Flask(__name__)

    app.secret_key = config.SECRET_KEY
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_HTTPONLY"] = True

    CORS(app, supports_credentials=True, origins=config.CORS_ORIGINS)

    app.register_blueprint(auth_bp)
    app.register_blueprint(clusters_bp)
    app.register_blueprint(ssh_bp)

    return app


app = create_app()

@app.route("/api/clusters/<cluster_id>/report", methods=["POST"])
def get_cluster_report(cluster_id):
    """
    Generate and download a PDF utilization report for a cluster.
 
    Body:
        { "start": "2025-10-01", "end": "2025-12-31" }
 
    Returns:
        PDF file download
    """
    if "user" not in session:
        return jsonify({"error": "Not authenticated"}), 401
 
    cluster = config.CLUSTERS.get(cluster_id)
    if not cluster:
        return jsonify({"error": f"Unknown cluster: {cluster_id}"}), 404
 
    body     = request.get_json(silent=True) or {}
    start    = body.get("start", "2025-10-01")
    end      = body.get("end",   "2025-12-31")
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
        return jsonify({"error": "Could not parse cluster output", "raw": raw}), 500
 
    parsed.pop("raw", None)
 
    # Generate PDF
    try:
        pdf_bytes = generate_utilization_report(parsed)
    except Exception as e:
        return jsonify({"error": "PDF generation failed", "detail": str(e)}), 500
 
    filename = f"hpc_report_{cluster_id}_{start}_to_{end}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5000)

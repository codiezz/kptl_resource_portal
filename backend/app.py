from ssh_layer.pdf_account_report import generate_account_report
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
from ssh_layer.slurm_report_parser import (
    parse_tres_utilization,
    parse_account_utilization
)
from ssh_layer.pdf_cluster_report import generate_enhanced_cluster_report
from ssh_layer.pdf_gpu_report import generate_gpu_report
from ssh_layer.pdf_account_report import generate_account_report
from ssh_layer.pdf_user_report import generate_user_report



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

@app.route("/api/clusters/<cluster_id>/report/cluster", methods=["POST"])
def get_enhanced_cluster_report(cluster_id):
    """
    Enhanced cluster utilization PDF report.
    Runs 3 Slurm commands: CPU utilization, GPU utilization, AccountUtilizationByUser.
    GPU command failure is handled gracefully — PDF still generates.
 
    POST body: { "start": "2025-10-01", "end": "2025-12-31" }
    Returns: downloadable PDF
    """
    if "user" not in session:
        return jsonify({"error": "Not authenticated"}), 401
 
    cluster = config.CLUSTERS.get(cluster_id)
    if not cluster:
        return jsonify({"error": f"Unknown cluster: {cluster_id}"}), 404
 
    body  = request.get_json(silent=True) or {}
    start = body.get("start", "2025-10-01")
    end   = body.get("end",   "2025-12-31")
 
    username = os.environ.get("HPC_USER", "")
    password = os.environ.get("HPC_PASS", "")
    if not username or not password:
        return jsonify({"error": "HPC credentials not set"}), 500
 
    host = cluster["host"]
    port = cluster["port"]
 
    # --- Command 1: CPU utilization ---
    cpu_raw = None
    try:
        cpu_raw = run_hpc_command(
            host=host, username=username, password=password, port=port, timeout=30,
            command=f"sreport cluster utilization Start={start} End={end} -t percent --tres=cpu"
        )
    except SSHError as e:
        return jsonify({"error": "SSH failed on CPU command", "detail": str(e)}), 502
 
    # --- Command 2: GPU utilization (graceful — failure does not abort PDF) ---
    gpu_raw = None
    try:
        gpu_raw = run_hpc_command(
            host=host, username=username, password=password, port=port, timeout=30,
            command=f"sreport cluster utilization Start={start} End={end} -t percent --tres=gres/gpu"
        )
    except SSHError:
        gpu_raw = None  # PDF will show "GPU data unavailable"
 
    # --- Command 3: Account utilization ---
    acct_raw = None
    try:
        acct_raw = run_hpc_command(
            host=host, username=username, password=password, port=port, timeout=30,
            command=f"sreport cluster AccountUtilizationByUser Start={start} End={end} -t hourper"
        )
    except SSHError:
        acct_raw = None  # PDF will show sections as unavailable
 
    # --- Parse all results ---
    cpu_data  = parse_tres_utilization(cpu_raw)  if cpu_raw  else {}
    gpu_data  = parse_tres_utilization(gpu_raw)  if gpu_raw  else {}
    acct_data = parse_account_utilization(acct_raw) if acct_raw else {}
 
    if not cpu_data.get("metrics"):
        return jsonify({"error": "Could not parse CPU utilization output", "raw": cpu_raw}), 500
 
    # Assemble data dict for PDF generator
    period = cpu_data.get("period", {})
    data = {
        "cluster":  cpu_data.get("cluster", cluster_id),
        "period":   period,
        "cpu":      cpu_data,
        "gpu":      gpu_data,
        "accounts": acct_data,
    }
 
    # --- Generate PDF ---
    try:
        pdf_bytes = generate_enhanced_cluster_report(data)
    except Exception as e:
        return jsonify({"error": "PDF generation failed", "detail": str(e)}), 500
 
    filename = f"cluster_report_{cluster_id}_{start}_to_{end}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )
@app.route("/api/clusters/<cluster_id>/report/gpu", methods=["POST"])
def get_gpu_report(cluster_id):
    """
    GPU-focused utilization PDF report.
    Runs: sreport cluster utilization -t percent --tres=gres/gpu
 
    POST body: { "start": "2025-10-01", "end": "2025-12-31" }
    Returns: downloadable PDF
 
    Graceful degradation: if GPU data unavailable, PDF still generates.
    """
    if "user" not in session:
        return jsonify({"error": "Not authenticated"}), 401
 
    cluster = config.CLUSTERS.get(cluster_id)
    if not cluster:
        return jsonify({"error": f"Unknown cluster: {cluster_id}"}), 404
 
    body  = request.get_json(silent=True) or {}
    start = body.get("start", "2025-10-01")
    end   = body.get("end",   "2025-12-31")
 
    username = os.environ.get("HPC_USER", "")
    password = os.environ.get("HPC_PASS", "")
    if not username or not password:
        return jsonify({"error": "HPC credentials not set"}), 500
 
    # GPU command — gres/gpu confirmed on fortytwo
    gpu_raw = None
    try:
        gpu_raw = run_hpc_command(
            host=cluster["host"],
            username=username,
            password=password,
            port=cluster["port"],
            timeout=30,
            command=f"sreport cluster utilization Start={start} End={end} -t percent --tres=gres/gpu"
        )
    except SSHAuthError as e:
        return jsonify({"error": "Authentication failed", "detail": str(e)}), 401
    except SSHTimeoutError:
        return jsonify({"error": "Cluster connection timed out"}), 504
    except SSHError as e:
        return jsonify({"error": "SSH failed", "detail": str(e)}), 502
 
    gpu_data = parse_tres_utilization(gpu_raw) if gpu_raw else {}
 
    # Use period from GPU data if available, else fall back to request params
    period = gpu_data.get("period", {"start": f"{start}T00:00:00", "end": f"{end}T23:59:59"})
 
    data = {
        "cluster": gpu_data.get("cluster", cluster_id),
        "period":  period,
        "gpu":     gpu_data,
    }
 
    try:
        pdf_bytes = generate_gpu_report(data)
    except Exception as e:
        return jsonify({"error": "PDF generation failed", "detail": str(e)}), 500
 
    filename = f"gpu_report_{cluster_id}_{start}_to_{end}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )
@app.route("/api/clusters/<cluster_id>/report/account", methods=["POST"])
def get_account_report(cluster_id):
    if "user" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    cluster = config.CLUSTERS.get(cluster_id)
    if not cluster:
        return jsonify({"error": f"Unknown cluster: {cluster_id}"}), 404
    body  = request.get_json(silent=True) or {}
    start = body.get("start", "2025-10-01")
    end   = body.get("end",   "2025-12-31")
    username = os.environ.get("HPC_USER", "")
    password = os.environ.get("HPC_PASS", "")
    if not username or not password:
        return jsonify({"error": "HPC credentials not set"}), 500
    acct_raw = None
    try:
        acct_raw = run_hpc_command(
            host=cluster["host"], username=username, password=password,
            port=cluster["port"], timeout=30,
            command=f"sreport cluster AccountUtilizationByUser Start={start} End={end} -t hourper"
        )
    except SSHAuthError as e:
        return jsonify({"error": "Authentication failed", "detail": str(e)}), 401
    except SSHTimeoutError:
        return jsonify({"error": "Cluster connection timed out"}), 504
    except SSHError as e:
        return jsonify({"error": "SSH failed", "detail": str(e)}), 502
    acct_data = parse_account_utilization(acct_raw) if acct_raw else {}
    period = acct_data.get("period", {"start": f"{start}T00:00:00", "end": f"{end}T23:59:59"})
    data = {
        "cluster":  acct_data.get("cluster", cluster_id),
        "period":   period,
        "accounts": acct_data,
    }
    try:
        pdf_bytes = generate_account_report(data)
    except Exception as e:
        return jsonify({"error": "PDF generation failed", "detail": str(e)}), 500
    return send_file(
        io.BytesIO(pdf_bytes), mimetype='application/pdf',
        as_attachment=True,
        download_name=f"account_report_{cluster_id}_{start}_to_{end}.pdf"
    )
@app.route("/api/clusters/<cluster_id>/report/user", methods=["POST"])
def get_user_report(cluster_id):
    if "user" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    cluster = config.CLUSTERS.get(cluster_id)
    if not cluster:
        return jsonify({"error": f"Unknown cluster: {cluster_id}"}), 404
    body  = request.get_json(silent=True) or {}
    start = body.get("start", "2025-10-01")
    end   = body.get("end",   "2025-12-31")
    username = os.environ.get("HPC_USER", "")
    password = os.environ.get("HPC_PASS", "")
    if not username or not password:
        return jsonify({"error": "HPC credentials not set"}), 500
    acct_raw = None
    try:
        acct_raw = run_hpc_command(
            host=cluster["host"], username=username, password=password,
            port=cluster["port"], timeout=30,
            command=f"sreport cluster AccountUtilizationByUser Start={start} End={end} -t hourper"
        )
    except SSHAuthError as e:
        return jsonify({"error": "Authentication failed", "detail": str(e)}), 401
    except SSHTimeoutError:
        return jsonify({"error": "Cluster connection timed out"}), 504
    except SSHError as e:
        return jsonify({"error": "SSH failed", "detail": str(e)}), 502
    acct_data = parse_account_utilization(acct_raw) if acct_raw else {}
    period = acct_data.get("period", {"start": f"{start}T00:00:00", "end": f"{end}T23:59:59"})
    data = {
        "cluster":  acct_data.get("cluster", cluster_id),
        "period":   period,
        "accounts": acct_data,
    }
    try:
        pdf_bytes = generate_user_report(data)
    except Exception as e:
        return jsonify({"error": "PDF generation failed", "detail": str(e)}), 500
    return send_file(
        io.BytesIO(pdf_bytes), mimetype='application/pdf',
        as_attachment=True,
        download_name=f"user_report_{cluster_id}_{start}_to_{end}.pdf"
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5000)

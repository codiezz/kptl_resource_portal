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
from slurm_report_parser import (
    parse_tres_utilization,
    parse_gpu_account_utilization,
    parse_gpu_account_pct,
    merge_gpu_account_data,
    parse_user_cpu_single,
)
from datetime import datetime
from pdf_gpu_report import generate_gpu_report

import config
from auth import role_required
from routes import auth_bp, clusters_bp, ssh_bp
from ssh_layer.slurm_report_parser import (
    parse_tres_utilization,
    parse_account_utilization
)
from ssh_layer.pdf_cluster_report import generate_enhanced_cluster_report
from ssh_layer.pdf_gpu_report import generate_gpu_report
from ssh_layer.pdf_account_report import generate_account_report
from ssh_layer.pdf_user_report import generate_user_report
from ssh_layer.account_helpers import filter_account, filter_gpu_account, build_account_user_table



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
 
    command=f"sreport cluster utilization Start={start} End={end} -t percent"
 
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

@app.route("/api/clusters/<cluster_id>/report/cluster", methods=["GET", "POST"])
def get_enhanced_cluster_report(cluster_id):
    print("=== CLUSTER ROUTE HIT ===")
    print("=== cluster_id:", cluster_id)
    print("=== session:", "user" in session)
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
        print("=== CPU RAW OUTPUT ===")
        print(repr(cpu_raw[:300]))
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
    GPU utilization PDF report — extended with account/user consumption pages.
 
    Runs 3 Slurm commands:
      1. sreport cluster utilization -t percent --tres=gres/gpu
         → Allocated/Idle/Down/Planned summary (existing pages)
      2. sreport cluster AccountUtilizationByUser -T gres/gpu
         → GPU hours per account/user (new accounts page)
      3. sreport cluster AccountUtilizationByUser -t percent -T gres/gpu
         → GPU usage % per account/user (new users page)
      4. hours 
    Commands 2 and 3 fail gracefully — PDF still generates from command 1.
 
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
 
    # --- Command 1: GPU utilization summary (existing) ---
    gpu_raw = None
    try:
        gpu_raw = run_hpc_command(
            host=host, username=username, password=password, port=port, timeout=30,
            command=f"sreport cluster utilization Start={start} End={end} -t percent --tres=gres/gpu"
        )
    except SSHAuthError as e:
        return jsonify({"error": "Authentication failed", "detail": str(e)}), 401
    except SSHTimeoutError:
        return jsonify({"error": "Cluster connection timed out"}), 504
    except SSHError as e:
        return jsonify({"error": "SSH failed", "detail": str(e)}), 502
 
    gpu_util = parse_tres_utilization(gpu_raw) if gpu_raw else {}
 
    # --- Command 2: GPU hours by account/user (graceful) ---
    gpu_hours_raw = None
    try:
        gpu_hours_raw = run_hpc_command(
            host=host, username=username, password=password, port=port, timeout=30,
            command=f"sreport cluster AccountUtilizationByUser Start={start} End={end} -T gres/gpu"
        )
    except SSHError:
        gpu_hours_raw = None
 
    # --- Command 3: GPU percentage by account/user (graceful) ---
    gpu_pct_raw = None
    try:
        gpu_pct_raw = run_hpc_command(
            host=host, username=username, password=password, port=port, timeout=30,
            command=f"sreport cluster AccountUtilizationByUser Start={start} End={end} -t percent -T gres/gpu"
        )
    except SSHError:
        gpu_pct_raw = None

 
    # --- Parse and merge ---
    hours_data = parse_gpu_account_utilization(gpu_hours_raw) if gpu_hours_raw else {}
    pct_data   = parse_gpu_account_pct(gpu_pct_raw)           if gpu_pct_raw   else {}
    gpu_accounts = merge_gpu_account_data(hours_data, pct_data) if hours_data else {}
 
    period = gpu_util.get("period", {"start": f"{start}T00:00:00", "end": f"{end}T23:59:59"})
 
    data = {
        "cluster":      gpu_util.get("cluster", cluster_id),
        "period":       period,
        "gpu":          gpu_util,
        "gpu_accounts": gpu_accounts,
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
 
@app.route("/api/clusters/<cluster_id>/report/accounts", methods=["GET","POST"])
def get_accounts_and_users(cluster_id):

    if "user" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    cluster = config.CLUSTERS.get(cluster_id)
    if not cluster:
        return jsonify({"error": f"Unknown cluster: {cluster_id}"}), 404

    if request.method == "GET":
        start = "2026-06-08"
        end = "2026-06-14"
    else:
        body = request.get_json(silent=True) or {}
        start = body.get("start", "2025-10-01")
        end = body.get("end", "2025-12-31")

    username = os.environ.get("HPC_USER", "")
    password = os.environ.get("HPC_PASS", "")

    if not username or not password:
        return jsonify({"error": "HPC credentials not set"}), 500

    try:
        raw_output = run_hpc_command(
            host=cluster["host"],
            username=username,
            password=password,
            port=cluster["port"],
            timeout=30,
            command=(
                f"sreport cluster "
                f"AccountUtilizationByUser "
                f"Start={start} End={end} -t hourper"
            )
        )

    except SSHAuthError as e:
        return jsonify({
            "error": "Authentication failed",
            "detail": str(e)
        }), 401

    except SSHTimeoutError:
        return jsonify({
            "error": "Cluster connection timed out"
        }), 504

    except SSHError as e:
        return jsonify({
            "error": "SSH failed",
            "detail": str(e)
        }), 502

    parsed = parse_account_utilization(raw_output)
    result = []
    for acct in parsed.get("accounts", []):
        account_name = acct.get("account")
        if not account_name:
           continue
        user_logins = [u.get("login") for u in acct.get("users", []) if u.get("login")]
        result.append({
            "name": account_name,
            "users": user_logins
    })

    return jsonify({
        "accounts": result
    }), 200

@app.route("/api/clusters/<cluster_id>/report/account", methods=["POST"])
@role_required("ADMIN")
def get_account_report(cluster_id):
    # if "user" not in session:
    #     return jsonify({"error": "Not authenticated"}), 401
    cluster = config.CLUSTERS.get(cluster_id)
    if not cluster:
        return jsonify({"error": f"Unknown cluster: {cluster_id}"}), 404
    body    = request.get_json(silent=True) or {}
    account = body.get("account")
    start   = body.get("start", "2025-10-01")
    end     = body.get("end",   "2025-12-31")

    if not account:
        return jsonify({"error": "account is required"}), 400

    username = os.environ.get("HPC_USER", "")
    password = os.environ.get("HPC_PASS", "")
    if not username or not password:
        return jsonify({"error": "HPC credentials not set"}), 500

    host = cluster["host"]
    port = cluster["port"]

    # --- Command 1: CPU (existing) ---
    acct_raw = None
    try:
        acct_raw = run_hpc_command(
            host=host, username=username, password=password,
            port=port, timeout=30,
            command=f"sreport cluster AccountUtilizationByUser Start={start} End={end} -t hourper"
        )
    except SSHAuthError as e:
        return jsonify({"error": "Authentication failed", "detail": str(e)}), 401
    except SSHTimeoutError:
        return jsonify({"error": "Cluster connection timed out"}), 504
    except SSHError as e:
        return jsonify({"error": "SSH failed", "detail": str(e)}), 502

    # --- Command 2: GPU hours (graceful) ---
    gpu_hours_raw = None
    try:
        gpu_hours_raw = run_hpc_command(
            host=host, username=username, password=password, port=port, timeout=30,
            command=f"sreport cluster AccountUtilizationByUser Start={start} End={end} -T gres/gpu"
        )
    except SSHError:
        gpu_hours_raw = None

    # --- Command 3: GPU percentage (graceful) ---
    gpu_pct_raw = None
    try:
        gpu_pct_raw = run_hpc_command(
            host=host, username=username, password=password, port=port, timeout=30,
            command=f"sreport cluster AccountUtilizationByUser Start={start} End={end} -t percent -T gres/gpu"
        )
    except SSHError:
        gpu_pct_raw = None

    # --- Parse ---
    acct_data  = parse_account_utilization(acct_raw) if acct_raw else {}
    hours_data = parse_gpu_account_utilization(gpu_hours_raw) if gpu_hours_raw else {}
    pct_data   = parse_gpu_account_pct(gpu_pct_raw)           if gpu_pct_raw   else {}
    gpu_accounts = merge_gpu_account_data(hours_data, pct_data) if hours_data else {}

    # --- Filter to selected account ---
    cpu_account = filter_account(acct_data, account)
    if cpu_account is None:
        return jsonify({"error": f"Account '{account}' not found in CPU report"}), 404

    gpu_account = filter_gpu_account(gpu_accounts, account)
    users = build_account_user_table(cpu_account, gpu_account)

    period = acct_data.get("period", {"start": f"{start}T00:00:00", "end": f"{end}T23:59:59"})

    
    
    try:
        print("===== CPU_ACCOUNT STRUCTURE =====")
        print(cpu_account)
        print("===== GPU_ACCOUNT STRUCTURE =====")
        print(gpu_account)

        data = {
            "cluster": acct_data.get("cluster", cluster_id),
            "account": account,
            "period":  period,
            "users":   users,
            "account_totals": {
                "cpu_hours": cpu_account.get("hours") or 0,
                "cpu_pct":   cpu_account.get("percentage") or 0,
                "gpu_hours": (gpu_account or {}).get("gpu_hours") or 0,
                "gpu_pct":   (gpu_account or {}).get("gpu_pct") or 0,
            },
        }

        print("\n===== ACCOUNT TOTALS =====")
        print(data["account_totals"])

        pdf_bytes = generate_account_report(data)   # only once
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": "PDF generation failed", "detail": str(e)}), 500
    return send_file(
        io.BytesIO(pdf_bytes), mimetype='application/pdf',
        as_attachment=True,
        download_name=f"account_report_{cluster_id}_{start}_to_{end}.pdf"
    )
@app.route("/api/clusters/<cluster_id>/report/user", methods=["POST"])
@role_required("ADMIN")
def get_user_report(cluster_id):
    # if "user" not in session:
    #     return jsonify({"error": "Not authenticated"}), 401

    cluster = config.CLUSTERS.get(cluster_id)
    if not cluster:
        return jsonify({"error": f"Unknown cluster: {cluster_id}"}), 404

    body     = request.get_json(silent=True) or {}
    start    = body.get("start", "2025-10-01")
    end      = body.get("end",   "2025-12-31")
    username = (body.get("username") or body.get("user") or "").strip()

    if not username:
        return jsonify({"error": "username is required"}), 400

    ssh_user = os.environ.get("HPC_USER", "")
    ssh_pass = os.environ.get("HPC_PASS", "")
    if not ssh_user or not ssh_pass:
        return jsonify({"error": "HPC credentials not set"}), 500

    def _ssh(cmd):
        return run_hpc_command(
            host=cluster["host"], username=ssh_user, password=ssh_pass,
            port=cluster["port"], timeout=30, command=cmd
        )

    # ── Command 1: all users — discover account + build peer list ─────────
    try:
        raw_cpu_all = _ssh(
            f"sreport cluster AccountUtilizationByUser"
            f" Start={start} End={end} -t hourper"
        )
    except SSHAuthError as e:
        return jsonify({"error": "Authentication failed", "detail": str(e)}), 401
    except SSHTimeoutError:
        return jsonify({"error": "Cluster connection timed out"}), 504
    except SSHError as e:
        return jsonify({"error": "SSH failed", "detail": str(e)}), 502

    all_data = parse_account_utilization(raw_cpu_all) if raw_cpu_all else {}

    # Discover which account this user belongs to
    discovered_account = None
    for acct in all_data.get("accounts", []):
        for u in acct.get("users", []):
            if u["login"] == username:
                discovered_account = acct["account"]
                break
        if discovered_account:
            break

    if not discovered_account:
        return jsonify({"error": f"User '{username}' not found in cluster data"}), 404

    # Build CPU peer list from the discovered account
    cpu_peers_raw = []
    for acct in all_data.get("accounts", []):
        if acct["account"] == discovered_account:
            cpu_peers_raw = acct.get("users", [])
            break

    # ── Command 2: precise single-user CPU row ────────────────────────────
    # Convert start to compact format MMDDYY that this subcommand expects
    try:
        from datetime import datetime as _dt
        compact_start = _dt.strptime(start, "%Y-%m-%d").strftime("%m%d%y")
    except ValueError:
        compact_start = start  # fall back to whatever was passed

    try:
        raw_cpu_user = _ssh(
            f"sreport cluster userutilizationbyaccount"
            f" -t hourper"
            f" account={discovered_account}"
            f" user={username}"
            f" start={compact_start}"
            f" end=now"
        )
    except SSHAuthError as e:
        return jsonify({"error": "Authentication failed", "detail": str(e)}), 401
    except SSHTimeoutError:
        return jsonify({"error": "Cluster connection timed out"}), 504
    except SSHError as e:
        return jsonify({"error": "SSH failed", "detail": str(e)}), 502

    user_cpu = parse_user_cpu_single(raw_cpu_user) if raw_cpu_user else {}

    # If Command 2 fails, fall back to the peer data we already have
    if not user_cpu:
        for u in cpu_peers_raw:
            if u["login"] == username:
                user_cpu = {
                    "login":      username,
                    "account":    discovered_account,
                    "hours":      u.get("hours") or 0,
                    "percentage": u.get("percentage") or 0.0,
                }
                break

    if not user_cpu:
        return jsonify({"error": f"Could not retrieve CPU data for '{username}'"}), 404

    # ── Commands 3 + 4: GPU hours and GPU percentage ──────────────────────
    try:
        raw_gpu_hours = _ssh(
            f"sreport cluster AccountUtilizationByUser"
            f" Start={start} End={end} -T gres/gpu"
        )
        raw_gpu_pct = _ssh(
            f"sreport cluster AccountUtilizationByUser"
            f" Start={start} End={end} -t percent -T gres/gpu"
        )
    except SSHAuthError as e:
        return jsonify({"error": "Authentication failed", "detail": str(e)}), 401
    except SSHTimeoutError:
        return jsonify({"error": "Cluster connection timed out"}), 504
    except SSHError as e:
        return jsonify({"error": "SSH failed", "detail": str(e)}), 502

    gpu_merged = merge_gpu_account_data(
        parse_gpu_account_utilization(raw_gpu_hours) if raw_gpu_hours else {},
        parse_gpu_account_pct(raw_gpu_pct)           if raw_gpu_pct   else {}
    )

    # Extract GPU peers from discovered account
    gpu_peers_raw  = []
    user_gpu_hours = 0.0
    user_gpu_pct   = None
    for acct in gpu_merged.get("accounts", []):
        if acct["account"] == discovered_account:
            gpu_peers_raw = acct.get("users", [])
            break

    for u in gpu_peers_raw:
        if u["login"] == username:
            user_gpu_hours = u.get("gpu_hours") or 0.0
            user_gpu_pct   = u.get("gpu_pct")
            break

    # ── In-memory analytics ───────────────────────────────────────────────
    import statistics

    cpu_peers_sorted = sorted(
        cpu_peers_raw, key=lambda u: u.get("hours") or 0, reverse=True
    )
    n_peers        = len(cpu_peers_sorted)
    cpu_values     = [u.get("hours") or 0 for u in cpu_peers_sorted]
    acct_cpu_total = sum(cpu_values)
    acct_cpu_avg   = statistics.mean(cpu_values)   if cpu_values else 0
    acct_cpu_med   = statistics.median(cpu_values) if cpu_values else 0

    user_cpu_hours = user_cpu.get("hours", 0)
    user_cpu_pct   = user_cpu.get("percentage", 0.0)

    cpu_rank = next(
        (i + 1 for i, u in enumerate(cpu_peers_sorted) if u["login"] == username),
        n_peers
    )
    cpu_top_pct   = round(100 * (1 - (cpu_rank - 1) / n_peers)) if n_peers else 0
    cpu_vs_avg    = round(user_cpu_hours / acct_cpu_avg, 2) if acct_cpu_avg else 0
    cpu_vs_median = round(user_cpu_hours / acct_cpu_med, 2) if acct_cpu_med else 0

    gpu_peers_sorted = sorted(
        gpu_peers_raw, key=lambda u: u.get("gpu_hours") or 0, reverse=True
    )
    gpu_values     = [u.get("gpu_hours") or 0 for u in gpu_peers_sorted]
    acct_gpu_total = sum(gpu_values)
    acct_gpu_avg   = statistics.mean(gpu_values) if gpu_values else 0

    n_gpu_peers = len(gpu_peers_sorted)
    gpu_rank = next(
        (i + 1 for i, u in enumerate(gpu_peers_sorted) if u["login"] == username),
        n_gpu_peers
    )
    gpu_top_pct = round(100 * (1 - (gpu_rank - 1) / n_gpu_peers)) if n_gpu_peers else 0
    gpu_vs_avg  = round(user_gpu_hours / acct_gpu_avg, 2) if acct_gpu_avg else 0

    # Resource profile
    def _profile(cpu_h, gpu_h, avg_cpu, avg_gpu):
        if gpu_h == 0 and cpu_h < avg_cpu * 0.3:
            return "Light User"
        if gpu_h == 0:
            return "CPU-Heavy"
        ratio = cpu_h / (gpu_h + 1)
        if ratio > 20:
            return "CPU-Heavy"
        elif ratio < 2:
            return "GPU-Heavy"
        elif cpu_h > avg_cpu * 2 or gpu_h > avg_gpu * 2:
            return "Power User"
        return "Balanced"

    resource_profile = _profile(user_cpu_hours, user_gpu_hours, acct_cpu_avg, acct_gpu_avg)

    # Observations
    observations = []
    observations.append(
        f"{username} contributed {user_cpu_pct:.2f}% of account CPU utilization."
    )
    if cpu_rank <= 5:
        observations.append(
            f"Ranked #{cpu_rank} highest CPU consumer in {discovered_account} "
            f"(top {100 - cpu_top_pct + 1}%)."
        )
    if gpu_peers_sorted and gpu_rank <= 5:
        observations.append(
            f"Ranked #{gpu_rank} highest GPU consumer in {discovered_account}."
        )
    if acct_cpu_med and cpu_vs_median != 1.0:
        direction = "exceeds" if cpu_vs_median > 1 else "is below"
        observations.append(
            f"CPU usage {direction} account median by {cpu_vs_median}×."
        )
    if acct_gpu_avg and gpu_vs_avg > 1:
        observations.append(
            f"GPU usage exceeds account average by {gpu_vs_avg}×."
        )
    if resource_profile == "Balanced":
        observations.append("Workload appears balanced between CPU and GPU.")
    elif resource_profile == "GPU-Heavy":
        observations.append("Workload is GPU-heavy relative to CPU usage.")
    elif resource_profile == "CPU-Heavy":
        observations.append("Workload is CPU-heavy with minimal GPU usage.")
    if cpu_vs_avg > 2 or gpu_vs_avg > 2:
        observations.append("Compute activity indicates sustained, intensive HPC usage.")

    # Peer lists with is_target flag
    cpu_peers_out = [
        {
            "login":     u["login"],
            "hours":     u.get("hours") or 0,
            "is_target": u["login"] == username,
        }
        for u in cpu_peers_sorted
    ]
    gpu_peers_out = [
        {
            "login":     u["login"],
            "gpu_hours": u.get("gpu_hours") or 0,
            "is_target": u["login"] == username,
        }
        for u in gpu_peers_sorted
    ]

    period    = all_data.get("period", {})
    start_str = (period.get("start") or start)[:10]
    end_str   = (period.get("end")   or end)[:10]

    enriched = {
        "username":         username,
        "account":          discovered_account,
        "cluster":          all_data.get("cluster", cluster_id),
        "start":            start_str,
        "end":              end_str,
        "generated_at":     datetime.now().strftime("%Y-%m-%d %H:%M"),

        "user_cpu_hours":   user_cpu_hours,
        "user_cpu_pct":     user_cpu_pct,
        "user_gpu_hours":   user_gpu_hours,
        "user_gpu_pct":     user_gpu_pct,

        "acct_cpu_total":   acct_cpu_total,
        "acct_gpu_total":   acct_gpu_total,
        "acct_cpu_avg":     round(acct_cpu_avg, 1),
        "acct_cpu_median":  round(acct_cpu_med, 1),
        "acct_gpu_avg":     round(acct_gpu_avg, 1),
        "n_peers":          n_peers,

        "cpu_vs_avg":       cpu_vs_avg,
        "cpu_vs_median":    cpu_vs_median,
        "gpu_vs_avg":       gpu_vs_avg,

        "cpu_rank":         cpu_rank,
        "gpu_rank":         gpu_rank,
        "cpu_top_pct":      cpu_top_pct,
        "gpu_top_pct":      gpu_top_pct,

        "resource_profile": resource_profile,
        "observations":     observations,

        "cpu_peers":        cpu_peers_out,
        "gpu_peers":        gpu_peers_out,
    }

    # ── Debug log — remove after testing ─────────────────────────────────
    import json
    print("=== USER REPORT ENRICHED PAYLOAD ===")
    print(json.dumps(enriched, indent=2, default=str))
    print("=====================================")

    try:
        pdf_bytes = generate_user_report(enriched)
    except Exception as e:
        return jsonify({"error": "PDF generation failed", "detail": str(e)}), 500

    return send_file(
        io.BytesIO(pdf_bytes), mimetype='application/pdf',
        as_attachment=True,
        download_name=f"user_report_{username}_{cluster_id}_{start}_to_{end}.pdf"
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5000)
import re
import logging
logger = logging.getLogger(__name__)
def filter_account(acct_data: dict, account_name: str) -> dict:
    """
    acct_data: output of parse_account_utilization(), shape:
        { "cluster": ..., "period": {...},
          "accounts": [ {"account": "...", "hours":, "percentage":, "users":[...]}, ... ],
          "cluster_total": {...} }
    Returns the single matching account dict, or None.
    """
    for a in acct_data.get("accounts", []):
        if (a.get("account") or "").strip().lower() == account_name.strip().lower():
            return a
    return None


def filter_gpu_account(gpu_accounts: dict, account_name: str) -> dict:
    """
    gpu_accounts: output of merge_gpu_account_data(), assumed same shape
        { "accounts": [ {"account": ..., "users": [...]}, ... ] }
    Returns the single matching account dict, or {}.
    """
    for a in gpu_accounts.get("accounts", []):
        if (a.get("account") or "").strip().lower() == account_name.strip().lower():
            return a
    return {}


def _classify_profile(cpu_pct: float, gpu_pct: float) -> str:
    if not cpu_pct and not gpu_pct:
        return "Inactive"
    if gpu_pct >= cpu_pct * 1.5 and gpu_pct > 5:
        return "GPU-heavy"
    if cpu_pct >= gpu_pct * 1.5:
        return "CPU-heavy"
    return "Balanced"

_USED_FIELD_RE = re.compile(r'^[\d,]+(\(\d+(\.\d+)?%\))?$|^\d+(\.\d+)?%$')

def build_account_user_table(cpu_account: dict, gpu_account: dict) -> list:
    cpu_users = (cpu_account or {}).get("users", [])
    gpu_users = (gpu_account or {}).get("users", [])

    cpu_hours_map = {}
    cpu_pct_map   = {}
    for u in cpu_users:
        login = (u.get('login') or '').strip()
        if not login or _USED_FIELD_RE.match(login):
            continue
        cpu_hours_map[login] = u.get('hours') or 0
        cpu_pct_map[login]   = u.get('percentage') or 0

    gpu_hours_map = {}
    gpu_pct_map   = {}
    for u in gpu_users:
        login = (u.get('login') or '').strip()
        if not login:
            continue
        gpu_hours_map[login] = u.get('gpu_hours') or 0
        gpu_pct_map[login]   = u.get('gpu_pct') or 0

    all_logins = set(cpu_hours_map) | set(gpu_hours_map)

    merged = []
    for login in all_logins:
        cpu_hours = cpu_hours_map.get(login, 0)
        cpu_pct   = cpu_pct_map.get(login, 0)
        gpu_hours = gpu_hours_map.get(login, 0)
        gpu_pct   = gpu_pct_map.get(login, 0)

        merged.append({
            "login": login,
            "cpu_hours": cpu_hours,
            "cpu_pct": cpu_pct,
            "gpu_hours": gpu_hours,
            "gpu_pct": gpu_pct,
            "profile": _classify_profile(cpu_pct, gpu_pct),
        })

    return merged
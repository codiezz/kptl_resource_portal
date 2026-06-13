"""
slurm_report_parser.py

Extended parsers for information-rich Slurm reporting.

Covers:
  - TRES-based cluster utilization (--tres=cpu, --tres=gres/gpu)
  - AccountUtilizationByUser (-t hourper)
  - Helper extractors for account/user dropdowns

All functions:
  - Accept raw string output from SSH executor
  - Strip ANSI escape codes
  - Return structured dicts / lists
  - Return {} or [] on failure — never raise
  - Log errors for debugging
"""

import re
import logging

logger = logging.getLogger(__name__)

# Strip ANSI color codes and terminal escape sequences
_ANSI = re.compile(r'\x1b(?:\[[0-9;]*[a-zA-Z]|\][^\x07]*\x07)')


def _clean(raw: str) -> str:
    """Strip ANSI codes, normalize line endings."""
    return _ANSI.sub('', (raw or '')).replace('\r\n', '\n').replace('\r', '\n')


def _extract_period(text: str) -> dict:
    """Extract start/end timestamps from sreport header line."""
    m = re.search(
        r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s*-\s*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})',
        text
    )
    if m:
        return {'start': m.group(1), 'end': m.group(2)}
    return {'start': None, 'end': None}


def _parse_used_field(value: str) -> dict:
    """
    Parse sreport Used field.

    Confirmed formats from fortytwo:
      "4388444(26.56%)"  →  {"hours": 4388444, "percentage": 26.56}
      "4388444"          →  {"hours": 4388444, "percentage": None}
      "26.56%"           →  {"hours": None,    "percentage": 26.56}
    """
    v = (value or '').strip()

    m = re.match(r'([\d,]+)\s*\(([\d.]+)%\)', v)
    if m:
        return {'hours': int(m.group(1).replace(',', '')), 'percentage': float(m.group(2))}

    m = re.match(r'^([\d,]+)$', v)
    if m:
        return {'hours': int(m.group(1).replace(',', '')), 'percentage': None}

    m = re.match(r'^([\d.]+)%$', v)
    if m:
        return {'hours': None, 'percentage': float(m.group(1))}

    return {'hours': None, 'percentage': None}


# ---------------------------------------------------------------------------
# parse_tres_utilization
# ---------------------------------------------------------------------------

def parse_tres_utilization(raw: str) -> dict:
    """
    Parse:
        sreport cluster utilization Start=<> End=<> -t percent --tres=cpu
        sreport cluster utilization Start=<> End=<> -t percent --tres=gres/gpu

    Confirmed column order on fortytwo:
        Cluster  TRES Name  Allocated  Down  PLND Dow  Idle  Planned  Reported

    GPU TRES name confirmed as: gres/gpu (NOT gpu)

    Returns:
    {
        "cluster":   "fortytwo",
        "tres_name": "cpu" | "gres/gpu",
        "period":    {"start": "...", "end": "..."},
        "metrics": {
            "allocated":    29.22,
            "down":          2.75,
            "planned_down":  0.0,
            "idle":         52.86,
            "planned":      15.18,
            "reported":    100.0
        }
    }
    Returns {} if data not parseable.
    """
    if not raw or not raw.strip():
        return {}
    try:
        clean = _clean(raw)
        result = {
            'cluster':   None,
            'tres_name': None,
            'period':    _extract_period(clean),
            'metrics':   {}
        }

        # Data row pattern: cluster  tres_name  XX.XX%  XX.XX%  XX.XX%  XX.XX%  XX.XX%  XX.XX%
        m = re.search(
            r'^\s*(\S+)\s+(\S+)\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%',
            clean, re.MULTILINE
        )
        if m:
            result['cluster']   = m.group(1)
            result['tres_name'] = m.group(2)
            result['metrics']   = {
                'allocated':    float(m.group(3)),
                'down':         float(m.group(4)),
                'planned_down': float(m.group(5)),
                'idle':         float(m.group(6)),
                'planned':      float(m.group(7)),
                'reported':     float(m.group(8)),
            }

        return result if result['metrics'] else {}

    except Exception as e:
        logger.error(f"parse_tres_utilization failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# parse_account_utilization
# ---------------------------------------------------------------------------

def parse_account_utilization(raw: str) -> dict:
    """
    Parse:
        sreport cluster AccountUtilizationByUser Start=<> End=<> -t hourper

    Confirmed output structure:
        Cluster  Account  Login  Proper Name  Used              Energy
        -------- -------- ------ ------------ ----------------- ------
        fortytwo                              16515432(100.00%)      0
        fortytwo  acct1                        4388444(26.56%)       0
        fortytwo  acct1   user1  Proper Name    100000(0.61%)        0

    Row type detection:
        identity tokens = everything between cluster name and Used field
        0 identity tokens after cluster → cluster total
        1 token → account subtotal
        2+ tokens → user row (account + login + optional proper name)

    Returns:
    {
        "cluster": "fortytwo",
        "period": {"start": "...", "end": "..."},
        "cluster_total": {"hours": 16515432, "percentage": 100.0},
        "accounts": [
            {
                "account": "acct1",
                "hours": 4388444,
                "percentage": 26.56,
                "users": [
                    {
                        "login": "user1",
                        "proper_name": "Proper Name",
                        "hours": 100000,
                        "percentage": 0.61
                    }
                ]
            }
        ]
    }
    Sorted by hours descending.
    Returns {} on failure.
    """
    if not raw or not raw.strip():
        return {}
    try:
        clean = _clean(raw)
        result = {
            'cluster':       None,
            'period':        _extract_period(clean),
            'cluster_total': None,
            'accounts':      []
        }

        lines    = clean.splitlines()
        in_data  = False
        acct_map = {}  # account_name → entry dict

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Separator line marks start of data
            if re.match(r'^-{3,}', stripped):
                in_data = True
                continue

            if not in_data:
                continue

            # Split fixed-width columns by 2+ spaces
            tokens = [t for t in re.split(r'\s{2,}', stripped) if t.strip()]

            if len(tokens) < 2:
                continue

            # Identify Used field (has digits, may have percentage in parens)
            # Energy is last (plain integer), Used is second-to-last
            # Handle case where Energy is missing
            last = tokens[-1]
            if re.match(r'^\d+$', last) and not re.search(r'\(', last):
                # Last is plain integer = Energy
                if len(tokens) < 2:
                    continue
                used_raw  = tokens[-2]
                identity  = tokens[:-2]
            else:
                # No Energy, last token is Used
                used_raw = tokens[-1]
                identity = tokens[:-1]

            # Validate used_raw starts with digits
            if not re.match(r'^\d', used_raw):
                continue

            used = _parse_used_field(used_raw)

            # Identity tokens: [cluster] [account] [login] [proper_name...]
            cluster_name = identity[0] if len(identity) > 0 else None
            account_name = identity[1] if len(identity) > 1 else None
            login        = identity[2] if len(identity) > 2 else None
            proper_name  = ' '.join(identity[3:]) if len(identity) > 3 else ''

            if not cluster_name:
                continue

            if not result['cluster']:
                result['cluster'] = cluster_name

            if account_name is None:
                # Cluster total row
                result['cluster_total'] = used

            elif login is None:
                # Account subtotal row
                if account_name not in acct_map:
                    entry = {
                        'account':    account_name,
                        'hours':      used['hours'],
                        'percentage': used['percentage'],
                        'users':      []
                    }
                    acct_map[account_name] = entry
                    result['accounts'].append(entry)
                else:
                    acct_map[account_name]['hours']      = used['hours']
                    acct_map[account_name]['percentage'] = used['percentage']

            else:
                # User row
                if account_name not in acct_map:
                    entry = {'account': account_name, 'hours': None, 'percentage': None, 'users': []}
                    acct_map[account_name] = entry
                    result['accounts'].append(entry)

                acct_map[account_name]['users'].append({
                    'login':       login,
                    'proper_name': proper_name,
                    'hours':       used['hours'],
                    'percentage':  used['percentage']
                })

        # Sort accounts by hours descending
        result['accounts'].sort(key=lambda a: a['hours'] or 0, reverse=True)

        return result

    except Exception as e:
        logger.error(f"parse_account_utilization failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# Helper extractors
# ---------------------------------------------------------------------------

def extract_accounts(raw: str) -> list:
    """Return list of account names from AccountUtilizationByUser output."""
    parsed = parse_account_utilization(raw)
    return [a['account'] for a in parsed.get('accounts', [])]


def extract_users_for_account(raw: str, account: str) -> list:
    """Return list of user logins for a specific account."""
    parsed = parse_account_utilization(raw)
    for a in parsed.get('accounts', []):
        if a['account'] == account:
            return [u['login'] for u in a.get('users', [])]
    return []


def get_all_users_sorted(account_data: dict, top_n: int = 15) -> list:
    """
    Flatten all users from parsed account data, sorted by hours desc.
    Used for top-users section in PDF.
    Returns list of user dicts with added 'account' field.
    """
    all_users = []
    for acct in account_data.get('accounts', []):
        for user in acct.get('users', []):
            all_users.append({**user, 'account': acct['account']})
    all_users.sort(key=lambda u: u['hours'] or 0, reverse=True)
    return all_users[:top_n]


# ---------------------------------------------------------------------------
# parse_gpu_account_utilization
# ---------------------------------------------------------------------------

def parse_gpu_account_utilization(raw: str) -> dict:
    """
    Parse:
        sreport cluster AccountUtilizationByUser Start=<> End=<> -T gres/gpu

    Confirmed output format from fortytwo:
        Cluster    Account    Login    Proper Name    TRES Name    Used
        --------   --------   -----    -----------    ---------    ----
        fortytwo   root                               gres/gpu     3739174
        fortytwo   iiser                              gres/gpu     3328062
        fortytwo   iiser      arnab                   gres/gpu     213443
        fortytwo   iiser      ashish                  gres/gpu     51019

    Key differences from parse_account_utilization():
      - Extra column: TRES Name (always "gres/gpu") — must be stripped before
        identity parsing
      - Used is a plain integer (TRES minutes), never hours(percentage%)
      - Proper Name is always blank on fortytwo — ignored safely
      - No Energy column
      - No cluster total row (fortytwo does not emit one for -T gres/gpu)

    Returns:
    {
        "cluster": "fortytwo",
        "period": {"start": "...", "end": "..."},
        "accounts": [
            {
                "account": "iiser",
                "gpu_minutes": 3328062,
                "users": [
                    {"login": "arnab",  "gpu_minutes": 213443},
                    {"login": "ashish", "gpu_minutes":  51019}
                ]
            },
            {
                "account": "root",
                "gpu_minutes": 3739174,
                "users": []
            }
        ]
    }
    Sorted by gpu_minutes descending.
    Returns {} on failure or empty input.
    """
    if not raw or not raw.strip():
        return {}
    try:
        clean = _clean(raw)
        result = {
            'cluster':  None,
            'period':   _extract_period(clean),
            'accounts': []
        }

        lines    = clean.splitlines()
        in_data  = False
        acct_map = {}

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if re.match(r'^-{3,}', stripped):
                in_data = True
                continue

            if not in_data:
                continue

            # Split by 2+ spaces — handles inconsistent left-aligned spacing
            tokens = [t for t in re.split(r'\s{2,}', stripped) if t.strip()]

            if len(tokens) < 3:
                continue

            # Last token is Used (plain integer TRES minutes)
            # Second-to-last is TRES Name (always "gres/gpu") — discard it
            # Everything before that is identity: cluster [account] [login] [proper_name]
            used_raw  = tokens[-1]
            # tokens[-2] is TRES Name — skip it
            identity  = tokens[:-2]

            # Validate Used is a plain integer
            if not re.match(r'^\d+$', used_raw):
                continue

            gpu_minutes = int(used_raw)

            cluster_name = identity[0] if len(identity) > 0 else None

            account_name = None
            login = None

            if len(identity) > 1:
             merged = identity[1].split(maxsplit=1)

             account_name = merged[0]

            if len(merged) > 1:
              login = merged[1]

# If login was already separated properly, keep it
            if len(identity) > 2:
                 login = identity[2]
            if not cluster_name:
                continue

            if not result['cluster']:
                result['cluster'] = cluster_name

            if account_name is None:
                # Cluster-level row with no account — skip (rare, ignore)
                continue

            elif login is None:
                # Account subtotal row
                if account_name not in acct_map:
                    entry = {
                        'account':     account_name,
                        'gpu_minutes': gpu_minutes,
                        'users':       []
                    }
                    acct_map[account_name] = entry
                    result['accounts'].append(entry)
                else:
                    acct_map[account_name]['gpu_minutes'] = gpu_minutes

            else:
                # User row
                if account_name not in acct_map:
                    entry = {
                        'account':     account_name,
                        'gpu_minutes': None,
                        'users':       []
                    }
                    acct_map[account_name] = entry
                    result['accounts'].append(entry)

                acct_map[account_name]['users'].append({
                    'login':       login,
                    'gpu_minutes': gpu_minutes
                })

        # Sort accounts by gpu_minutes descending
        result['accounts'].sort(key=lambda a: a['gpu_minutes'] or 0, reverse=True)

        return result if result['accounts'] else {}

    except Exception as e:
        logger.error(f"parse_gpu_account_utilization failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# parse_gpu_account_pct
# ---------------------------------------------------------------------------

def parse_gpu_account_pct(raw: str) -> dict:
    """
    Parse:
        sreport cluster AccountUtilizationByUser Start=<> End=<> -t percent -T gres/gpu

    This command produces percentage output WITHOUT a TRES Name column.
    Confirmed format:
        Cluster    Account    Login    Proper Name    Used
        --------   --------   -----    -----------    ----
        fortytwo   root                               49.74%
        fortytwo   iiser                              44.27%
        fortytwo   iiser      arnab                    2.84%
        fortytwo   iiser      madhu                    9.38%

    Key differences from parse_gpu_account_utilization():
      - No TRES Name column
      - Used is a percentage string (e.g. "49.74%"), not plain integer
      - Same row structure: cluster, [account], [login], [proper_name], used

    Returns:
    {
        "cluster": "fortytwo",
        "period": {"start": "...", "end": "..."},
        "accounts": [
            {
                "account": "root",
                "gpu_pct": 49.74,
                "users": [...]
            }
        ]
    }
    Returns {} on failure or empty input.
    """
    if not raw or not raw.strip():
        return {}
    try:
        clean = _clean(raw)
        result = {
            'cluster':  None,
            'period':   _extract_period(clean),
            'accounts': []
        }

        lines    = clean.splitlines()
        in_data  = False
        acct_map = {}

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if re.match(r'^-{3,}', stripped):
                in_data = True
                continue

            if not in_data:
                continue

            tokens = [t for t in re.split(r'\s{2,}', stripped) if t.strip()]

            if len(tokens) < 2:
                continue

            # Last token is Used — must be a percentage
            used_raw = tokens[-1]
            identity = tokens[:-1]

            pct_match = re.match(r'^([\d.]+)%$', used_raw)
            if not pct_match:
                continue

            gpu_pct      = float(pct_match.group(1))
            cluster_name = identity[0] if len(identity) > 0 else None

            account_name = None
            login = None

            if len(identity) > 1:
                merged = identity[1].split(maxsplit=1)

                account_name = merged[0]

            if len(merged) > 1:
             login = merged[1]

# If login was already separated properly, keep it
            if len(identity) > 2:
                login = identity[2]

            if not cluster_name:
                continue

            if not result['cluster']:
                result['cluster'] = cluster_name

            if account_name is None:
                continue  # cluster total row — skip

            elif login is None:
                if account_name not in acct_map:
                    entry = {'account': account_name, 'gpu_pct': gpu_pct, 'users': []}
                    acct_map[account_name] = entry
                    result['accounts'].append(entry)
                else:
                    acct_map[account_name]['gpu_pct'] = gpu_pct

            else:
                if account_name not in acct_map:
                    entry = {'account': account_name, 'gpu_pct': None, 'users': []}
                    acct_map[account_name] = entry
                    result['accounts'].append(entry)

                acct_map[account_name]['users'].append({
                    'login':   login,
                    'gpu_pct': gpu_pct
                })

        result['accounts'].sort(key=lambda a: a['gpu_pct'] or 0, reverse=True)
        return result if result['accounts'] else {}

    except Exception as e:
        logger.error(f"parse_gpu_account_pct failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# merge_gpu_account_data
# ---------------------------------------------------------------------------

def merge_gpu_account_data(hours_data: dict, pct_data: dict) -> dict:
    """
    Merge GPU hours data and GPU percentage data into one unified structure.

    Takes parse_gpu_account_utilization() output (has gpu_minutes → converts
    to gpu_hours) and merges in percentage values from parse_gpu_account_pct().

    GPU minutes → GPU hours: gpu_hours = round(gpu_minutes / 60, 2)

    Returns:
    {
        "cluster": "fortytwo",
        "period": {...},
        "accounts": [
            {
                "account": "iiser",
                "gpu_hours": 55467.7,    # converted from minutes
                "gpu_pct": 44.27,        # from pct_data, None if unavailable
                "users": [
                    {
                        "login": "arnab",
                        "gpu_hours": 3557.4,
                        "gpu_pct": 2.84
                    }
                ]
            }
        ]
    }
    Users with 0 gpu_hours are kept (filtered at PDF layer per requirement).
    """
    if not hours_data:
        return {}
    print("\n========== GPU DEBUG ==========")
    print("HOURS DATA:")

    for acct in hours_data.get('accounts', []):
        print("ACCOUNT:", acct.get('account'))
        print("USERS:", acct.get('users'))
        print("---")

        print("PCT DATA:")

    for acct in pct_data.get('accounts', []):
        print("ACCOUNT:", acct.get('account'))
        print("USERS:", acct.get('users'))
        print("---")

    # Build pct lookup maps
    acct_pct_map = {}
    user_pct_map = {}  # (account, login) -> pct

    for acct in pct_data.get('accounts', []):
        acct_pct_map[acct['account']] = acct.get('gpu_pct')
        for u in acct.get('users', []):
            user_pct_map[(acct['account'], u['login'])] = u.get('gpu_pct')

    merged_accounts = []
    print("\nRAW HOURS DATA:")
    for a in hours_data.get('accounts', []):
        print(a)
    for acct in hours_data.get('accounts', []):
        acct_name  = acct['account']
        gpu_min    = acct.get('gpu_minutes') or 0
        gpu_hours  = round(gpu_min / 60, 2)

        merged_users = []
        for u in acct.get('users', []):
            u_min   = u.get('gpu_minutes') or 0
            u_hours = round(u_min / 60, 2)
            merged_users.append({
                'login':     u['login'],
                'gpu_hours': u_hours,
                'gpu_pct':   user_pct_map.get((acct_name, u['login']))
            })

        # Sort users by gpu_hours desc
        merged_users.sort(key=lambda u: u['gpu_hours'], reverse=True)

        merged_accounts.append({
            'account':   acct_name,
            'gpu_hours': gpu_hours,
            'gpu_pct':   acct_pct_map.get(acct_name),
            'users':     merged_users
        })

    # Sort accounts by gpu_hours desc
    merged_accounts.sort(key=lambda a: a['gpu_hours'], reverse=True)

    return {
        'cluster':  hours_data.get('cluster'),
        'period':   hours_data.get('period', {}),
        'accounts': merged_accounts
    }


# ---------------------------------------------------------------------------
# Self-tests — run directly to verify
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    # --- Test _parse_used_field ---
    assert _parse_used_field('4388444(26.56%)') == {'hours': 4388444, 'percentage': 26.56}
    assert _parse_used_field('4388444') == {'hours': 4388444, 'percentage': None}
    assert _parse_used_field('26.56%') == {'hours': None, 'percentage': 26.56}
    print("[PASS] _parse_used_field")

    # --- Test parse_tres_utilization (CPU) ---
    cpu_raw = """\
Cluster Utilization 2025-10-01T00:00:00 - 2025-12-31T23:59:59
Usage reported in Percentage of Total

  Cluster   TRES Name  Allocated      Down  PLND Dow      Idle   Planned  Reported
--------- ----------- ---------- --------- --------- --------- --------- ---------
 fortytwo         cpu     29.22%     2.75%     0.00%    52.86%    15.18%   100.00%
"""
    r = parse_tres_utilization(cpu_raw)
    assert r['tres_name'] == 'cpu', f"Got: {r['tres_name']}"
    assert r['metrics']['allocated'] == 29.22
    assert r['metrics']['idle'] == 52.86
    assert r['period']['start'] == '2025-10-01T00:00:00'
    print("[PASS] parse_tres_utilization (cpu)")

    # --- Test parse_tres_utilization (GPU) ---
    gpu_raw = """\
Cluster Utilization 2025-10-01T00:00:00 - 2025-12-31T23:59:59
Usage reported in Percentage of Total

  Cluster   TRES Name  Allocated      Down  PLND Dow      Idle   Planned  Reported
--------- ----------- ---------- --------- --------- --------- --------- ---------
 fortytwo    gres/gpu     49.74%     2.44%     0.00%    47.82%     0.00%   100.65%
"""
    r = parse_tres_utilization(gpu_raw)
    assert r['tres_name'] == 'gres/gpu', f"Got: {r['tres_name']}"
    assert r['metrics']['allocated'] == 49.74
    assert r['metrics']['idle'] == 47.82
    print("[PASS] parse_tres_utilization (gres/gpu)")

    # --- Test parse_tres_utilization (empty) ---
    assert parse_tres_utilization('') == {}
    assert parse_tres_utilization(None) == {}
    print("[PASS] parse_tres_utilization (empty/None graceful)")

    # --- Test parse_account_utilization ---
    acct_raw = """\
Cluster/Account/User Utilization 2025-10-01T00:00:00 - 2025-12-31T23:59:59
Usage reported in CPU Hours

   Cluster    Account       Login     Proper Name     Used   Energy
---------- ---------- ----------- --------------- -------- --------
  fortytwo                                        16515432(100.00%)        0
  fortytwo       acct1                             4388444(26.56%)        0
  fortytwo       acct1      user1        Full Name   100000(0.61%)        0
  fortytwo       acct1      user2        Other One   200000(1.21%)        0
  fortytwo       acct2                             2000000(12.11%)        0
  fortytwo       acct2      user3        Someone     500000(3.03%)        0
"""
    r = parse_account_utilization(acct_raw)
    assert r['cluster'] == 'fortytwo', f"Got: {r['cluster']}"
    assert r['cluster_total']['hours'] == 16515432
    assert r['cluster_total']['percentage'] == 100.0
    assert len(r['accounts']) == 2
    # Sorted by hours: acct1 (4388444) > acct2 (2000000)
    assert r['accounts'][0]['account'] == 'acct1'
    assert len(r['accounts'][0]['users']) == 2
    assert r['accounts'][0]['users'][0]['login'] in ['user1', 'user2']
    print("[PASS] parse_account_utilization")

    # --- Test extract_accounts ---
    accounts = extract_accounts(acct_raw)
    assert 'acct1' in accounts and 'acct2' in accounts
    print("[PASS] extract_accounts")

    # --- Test get_all_users_sorted ---
    users = get_all_users_sorted(r, top_n=5)
    assert users[0]['hours'] >= users[1]['hours']  # sorted desc
    print("[PASS] get_all_users_sorted")

    # --- Test parse_gpu_account_utilization ---
    gpu_acct_raw = """\
Cluster/Account/User Utilization 2025-10-01T00:00:00 - 2025-12-31T23:59:59
Usage reported in TRES Minutes

   Cluster    Account       Login     Proper Name    TRES Name         Used
---------- ---------- ----------- ---------------  ----------  -----------
  fortytwo       root                               gres/gpu      3739174
  fortytwo      iiser                               gres/gpu      3328062
  fortytwo      iiser       arnab                   gres/gpu       213443
  fortytwo      iiser      ashish                   gres/gpu        51019
"""
    r = parse_gpu_account_utilization(gpu_acct_raw)
    assert r['cluster'] == 'fortytwo',           f"cluster: {r['cluster']}"
    assert len(r['accounts']) == 2,              f"accounts: {len(r['accounts'])}"
    # sorted by gpu_minutes desc: root(3739174) > iiser(3328062)
    assert r['accounts'][0]['account'] == 'root',  f"top account: {r['accounts'][0]['account']}"
    assert r['accounts'][0]['gpu_minutes'] == 3739174
    assert r['accounts'][1]['account'] == 'iiser'
    assert r['accounts'][1]['gpu_minutes'] == 3328062
    assert len(r['accounts'][1]['users']) == 2
    logins = [u['login'] for u in r['accounts'][1]['users']]
    assert 'arnab'  in logins, f"logins: {logins}"
    assert 'ashish' in logins, f"logins: {logins}"
    assert r['accounts'][1]['users'][0]['gpu_minutes'] in [213443, 51019]
    print("[PASS] parse_gpu_account_utilization")

    # --- Test parse_gpu_account_utilization (empty/None) ---
    assert parse_gpu_account_utilization('') == {}
    assert parse_gpu_account_utilization(None) == {}
    print("[PASS] parse_gpu_account_utilization (empty/None graceful)")

    # --- Test parse_gpu_account_pct ---
    gpu_pct_raw = """\
Cluster/Account/User Utilization 2025-10-01T00:00:00 - 2025-12-31T23:59:59
Usage reported in Percentage of TRES

   Cluster    Account       Login     Proper Name     Used
---------- ---------- ----------- ---------------  --------
  fortytwo       root                               49.74%
  fortytwo      iiser                               44.27%
  fortytwo      iiser       arnab                    2.84%
  fortytwo      iiser      ashish                    9.38%
"""
    r = parse_gpu_account_pct(gpu_pct_raw)
    assert r['cluster'] == 'fortytwo',              f"cluster: {r['cluster']}"
    assert len(r['accounts']) == 2,                 f"accounts: {len(r['accounts'])}"
    # sorted by pct desc: root(49.74) > iiser(44.27)
    assert r['accounts'][0]['account'] == 'root',   f"top: {r['accounts'][0]['account']}"
    assert r['accounts'][0]['gpu_pct'] == 49.74
    assert r['accounts'][1]['gpu_pct'] == 44.27
    assert len(r['accounts'][1]['users']) == 2
    print("[PASS] parse_gpu_account_pct")

    assert parse_gpu_account_pct('') == {}
    assert parse_gpu_account_pct(None) == {}
    print("[PASS] parse_gpu_account_pct (empty/None graceful)")

    # --- Test merge_gpu_account_data ---
    hours_input = {
        'cluster': 'fortytwo',
        'period': {'start': '2025-10-01T00:00:00', 'end': '2025-12-31T23:59:59'},
        'accounts': [
            {
                'account': 'iiser',
                'gpu_minutes': 3328062,
                'users': [
                    {'login': 'arnab',  'gpu_minutes': 213443},
                    {'login': 'ashish', 'gpu_minutes':  51019},
                ]
            },
            {
                'account': 'root',
                'gpu_minutes': 3739174,
                'users': []
            }
        ]
    }
    pct_input = {
        'accounts': [
            {'account': 'root',  'gpu_pct': 49.74, 'users': []},
            {'account': 'iiser', 'gpu_pct': 44.27, 'users': [
                {'login': 'arnab',  'gpu_pct': 2.84},
                {'login': 'ashish', 'gpu_pct': 9.38},
            ]},
        ]
    }
    m = merge_gpu_account_data(hours_input, pct_input)
    assert m['cluster'] == 'fortytwo'
    assert len(m['accounts']) == 2
    # sorted by gpu_hours desc: root (3739174/60=62319.57) > iiser (3328062/60=55467.7)
    assert m['accounts'][0]['account'] == 'root'
    assert m['accounts'][0]['gpu_hours'] == round(3739174 / 60, 2)
    assert m['accounts'][0]['gpu_pct'] == 49.74
    assert m['accounts'][1]['account'] == 'iiser'
    assert m['accounts'][1]['gpu_hours'] == round(3328062 / 60, 2)
    assert m['accounts'][1]['gpu_pct'] == 44.27
    # users sorted by gpu_hours desc: ashish(51019/60=850.32) vs arnab(213443/60=3557.38)
    assert m['accounts'][1]['users'][0]['login'] == 'arnab'
    assert m['accounts'][1]['users'][0]['gpu_hours'] == round(213443 / 60, 2)
    assert m['accounts'][1]['users'][0]['gpu_pct'] == 2.84
    print("[PASS] merge_gpu_account_data")

    # merge with empty pct — pct fields become None, hours still present
    m2 = merge_gpu_account_data(hours_input, {})
    assert m2['accounts'][0]['gpu_pct'] is None
    assert m2['accounts'][0]['gpu_hours'] > 0
    print("[PASS] merge_gpu_account_data (empty pct graceful)")

    print("\nAll parser tests passed.")
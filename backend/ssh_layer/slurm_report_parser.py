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
    return raw.replace('\r\n', '\n').replace('\r', '\n')    

def _extract_period(clean: str) -> dict:
    """Extract start/end timestamps from sreport header."""
    period = {}
    m = re.search(r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})', clean)
    if m:
        period['start'] = m.group(1)
    matches = list(re.finditer(r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})', clean))
    if len(matches) >= 2:
        period['end'] = matches[-1].group(1)
    return period


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
 
        # FIX: Try 8-column pattern first (with --tres flag: cluster tres_name pct*6)
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
            return result
 
        # FIX: 7-column fallback for plain `sreport cluster utilization -t percent`
        # (no --tres flag → no tres_name column)
        m = re.search(
            r'^\s*(\S+)\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%',
            clean, re.MULTILINE
        )
        if m:
            result['cluster']   = m.group(1)
            result['tres_name'] = 'cpu'   # implicit when no --tres given
            result['metrics']   = {
                'allocated':    float(m.group(2)),
                'down':         float(m.group(3)),
                'planned_down': float(m.group(4)),
                'idle':         float(m.group(5)),
                'planned':      float(m.group(6)),
                'reported':     float(m.group(7)),
            }
            return result
 
        return {}
 
    except Exception as e:
        logger.error(f"parse_tres_utilization failed: {e}")
        return {}
 

# ---------------------------------------------------------------------------
# parse_account_utilization
# ---------------------------------------------------------------------------

def parse_account_utilization(raw: str) -> dict:
    print("PARSER VERSION: SSH_LAYER")
 
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
 
            # FIX: -t hourper columns are:
            #   Cluster  Account  Login  Proper Name  Used(hours(pct))  Energy
            # "Used" token looks like: 4388444(26.56%)
            # Proper Name may be empty or multi-word; Energy column may be absent.
            # Strategy: pull the Used token by pattern, everything before is identity.
            m = m = re.search(r'(\d[\d,]*)\(([\d.]+)%\)\s*\d+\([\d.]+%\)\s*$', stripped)
            if not m:
                continue
 
            hours      = int(m.group(1).replace(',', ''))
            percentage = float(m.group(2))
            used       = {'hours': hours, 'percentage': percentage}
 
            # Everything before the Used token is identity columns
            identity_str = stripped[:m.start()].strip()
            identity     = identity_str.split()
 
            cluster_name = identity[0] if len(identity) > 0 else None
            account_name = identity[1] if len(identity) > 1 else None
            login        = identity[2] if len(identity) > 2 else None
 
            # FIX: proper_name may occupy identity[3..] — ignore it, we only need login
            # If login looks like a Used token someone accidentally left, clear it
            if login and re.match(r'^\d+\([\d.]+%\)$', login):
                login = None
 
            if not cluster_name:
                continue
 
            if not result['cluster']:
                result['cluster'] = cluster_name
 
            if account_name is None:
                result['cluster_total'] = used
 
            elif login is None:
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
                if account_name not in acct_map:
                    entry = {
                        'account':    account_name,
                        'hours':      None,
                        'percentage': None,
                        'users':      []
                    }
                    acct_map[account_name] = entry
                    result['accounts'].append(entry)
 
                acct_map[account_name]['users'].append({
                    'login':       login,
                    'proper_name': '',   # FIX: proper_name skipped cleanly
                    'hours':       used['hours'],
                    'percentage':  used['percentage'],
                })
 
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

            used_raw = tokens[-1]
            identity = tokens[:-1]

            # FIX: strip TRES Name column (e.g. 'gres/gpu') from identity
            identity = [t for t in identity if not t.startswith('gres/')]

            if not re.match(r'^\d+$', used_raw):
                continue

            gpu_minutes  = int(used_raw)
            cluster_name = identity[0] if len(identity) > 0 else None

            account_name = None
            login        = None

            if len(identity) > 1:
                merged       = identity[1].split(maxsplit=1)
                account_name = merged[0]
                if len(merged) > 1:
                    login = merged[1]

            if len(identity) > 2:
                login = identity[2]

            if not cluster_name:
                continue

            if not result['cluster']:
                result['cluster'] = cluster_name

            if account_name is None:
                continue

            elif login is None:
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

        result['accounts'].sort(key=lambda a: a['gpu_minutes'] or 0, reverse=True)
        return result if result['accounts'] else {}

    except Exception as e:
        logger.error(f"parse_gpu_account_utilization failed: {e}")
        return {}


def parse_gpu_account_pct(raw: str) -> dict:
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

            used_raw = tokens[-1]
            identity = tokens[:-1]

            # FIX: strip TRES Name column (e.g. 'gres/gpu') from identity
            identity = [t for t in identity if not t.startswith('gres/')]

            pct_match = re.match(r'^([\d.]+)%$', used_raw)
            if not pct_match:
                continue

            gpu_pct      = float(pct_match.group(1))
            cluster_name = identity[0] if len(identity) > 0 else None

            account_name = None
            login        = None

            if len(identity) > 1:
                merged       = identity[1].split(maxsplit=1)
                account_name = merged[0]
                if len(merged) > 1:
                    login = merged[1]

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
"""
slurm_parser.py

Parses raw text output from Slurm commands into structured Python dicts
suitable for JSON serialization and frontend charting.

Each parser is a pure function: str -> dict | list
No SSH, no state, no side effects. Easy to unit test with captured output.
"""

import re
from typing import Optional


# ---------------------------------------------------------------------------
# sreport cluster Utilization -t percent
# ---------------------------------------------------------------------------

def parse_cluster_utilization(raw: str) -> dict:
    # Strip ANSI escape codes (terminal color codes)
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m|\x1b\][^\x07]*\x07')
    clean = ansi_escape.sub('', raw)

    result = {
        "cluster": None,
        "period": {"start": None, "end": None},
        "metrics": {},
        "raw": raw,
    }

    # Extract period
    period_match = re.search(
        r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s*-\s*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})',
        clean
    )
    if period_match:
        result["period"]["start"] = period_match.group(1)
        result["period"]["end"] = period_match.group(2)

    # Extract data row — skip separator lines (---), find cluster data
    data_match = re.search(
        r'^\s*(\S+)\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%',
        clean,
        re.MULTILINE
    )
    if data_match:
        result["cluster"] = data_match.group(1)
        result["metrics"] = {
            "allocated":    float(data_match.group(2)),
            "down":         float(data_match.group(3)),
            "planned_down": float(data_match.group(4)),
            "idle":         float(data_match.group(5)),
            "planned":      float(data_match.group(6)),
            "reported":     float(data_match.group(7)),
        }

    return result


# ---------------------------------------------------------------------------
# squeue output
# ---------------------------------------------------------------------------

def parse_squeue(raw: str) -> list[dict]:
    """
    Parse output of:
        squeue --format="%i %j %u %T %M %l %D %R" --noheader

    Returns list of job dicts.
    Adjust format string in Flask endpoint to match what your clusters output.
    """
    jobs = []
    for line in raw.strip().splitlines():
        parts = line.split()
        if len(parts) < 8:
            continue
        jobs.append({
            "job_id":    parts[0],
            "name":      parts[1],
            "user":      parts[2],
            "state":     parts[3],
            "time":      parts[4],
            "time_limit":parts[5],
            "nodes":     parts[6],
            "reason":    ' '.join(parts[7:]),
        })
    return jobs


# ---------------------------------------------------------------------------
# sinfo output
# ---------------------------------------------------------------------------

def parse_sinfo(raw: str) -> list[dict]:
    """
    Parse output of:
        sinfo --format="%P %a %l %D %T %N" --noheader
    """
    partitions = []
    for line in raw.strip().splitlines():
        parts = line.split()
        if len(parts) < 6:
            continue
        partitions.append({
            "partition": parts[0],
            "avail":     parts[1],
            "timelimit": parts[2],
            "nodes":     parts[3],
            "state":     parts[4],
            "nodelist":  parts[5],
        })
    return partitions


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    sample_utilization = """
Cluster Utilization 2025-10-01T00:00:00 - 2025-12-30T23:59:59
Usage reported in Percentage of Total

Cluster    Allocated    Down    PLND Dow    Idle    Planned    Reported

fortytwo    29.22%    2.75%    0.00%    52.86%    15.18%    100.00%
"""

    result = parse_cluster_utilization(sample_utilization)
    assert result["cluster"] == "fortytwo", f"cluster mismatch: {result['cluster']}"
    assert result["metrics"]["allocated"] == 29.22
    assert result["metrics"]["idle"] == 52.86
    assert result["period"]["start"] == "2025-10-01T00:00:00"
    print("[PASS] parse_cluster_utilization")

    # Edge: cluster with different name
    sample2 = """
Cluster Utilization 2025-01-01T00:00:00 - 2025-03-31T23:59:59
Usage reported in Percentage of Total

Cluster    Allocated    Down    PLND Dow    Idle    Planned    Reported

alpha99    55.10%    0.50%    1.00%    40.00%    3.40%    100.00%
"""
    r2 = parse_cluster_utilization(sample2)
    assert r2["cluster"] == "alpha99"
    assert r2["metrics"]["allocated"] == 55.10
    print("[PASS] parse_cluster_utilization (second cluster)")

    print("\nAll parser tests passed.")
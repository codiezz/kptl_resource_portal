import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ssh_layer'))
from captcha_parser import parse_captcha
from slurm_parser import parse_cluster_utilization
from ssh_executor import SSHExecutor, CommandResult

MOCK_SERVER_PATH = "/tmp/mock_server.py"

def test_captcha_parser():
    cases = [
        ("Observe\n\n( t | w | F | W | b | O | d | x )\n\nType the string above:", "twFWbOdx"),
        ("( A | 3 | z )\nType the string above:", "A3z"),
        ("( x | Y | 9 )\nType the string above:", "xY9"),
        ("Password:", None),
    ]
    for text, expected in cases:
        r = parse_captcha(text)
        assert r == expected, f"Input: {text!r}\nExpected: {expected!r}, got: {r!r}"
    print("[PASS] captcha parser (4 cases)")

def test_slurm_parser():
    sample = (
        "Cluster Utilization 2025-10-01T00:00:00 - 2025-12-30T23:59:59\n"
        "Usage reported in Percentage of Total\n\n"
        "Cluster    Allocated    Down    PLND Dow    Idle    Planned    Reported\n\n"
        "fortytwo    29.22%    2.75%    0.00%    52.86%    15.18%    100.00%\n"
    )
    p = parse_cluster_utilization(sample)
    assert p["cluster"] == "fortytwo"
    assert p["metrics"]["allocated"] == 29.22
    assert p["metrics"]["idle"] == 52.86
    assert p["period"]["start"] == "2025-10-01T00:00:00"
    print("[PASS] slurm parser")

def test_full_mock_ssh_flow():
    import pexpect

    # Use SSHExecutor but override the ssh_binary to point to our mock
    # We monkey-patch spawn to use our mock server instead of real ssh
    executor = SSHExecutor(host="mock-hpc", port=22, timeout=10)

    # Patch pexpect.spawn inside executor context
    original_spawn = pexpect.spawn

    class MockChild:
        """Wraps a pexpect process running our mock server."""
        def __init__(self):
            self._child = original_spawn(
                sys.executable, [MOCK_SERVER_PATH],
                timeout=10, encoding='utf-8'
            )
        def __getattr__(self, name):
            return getattr(self._child, name)

    import ssh_executor as mod
    original_pexpect_spawn = mod.pexpect.spawn

    def mock_spawn(binary, args, **kwargs):
        return original_spawn(sys.executable, [MOCK_SERVER_PATH], **kwargs)

    mod.pexpect.spawn = mock_spawn
    try:
        result = executor.run(
            username="testuser",
            password="correctpassword",
            command="sreport cluster Utilization -t percent"
        )
    finally:
        mod.pexpect.spawn = original_pexpect_spawn

    print("[PASS] full mock SSH flow")
    print(f"Captured output:\n{result.stdout}\n")

    parsed = parse_cluster_utilization(result.stdout)
    assert parsed["cluster"] == "fortytwo", f"cluster={parsed['cluster']!r}"
    assert parsed["metrics"]["allocated"] == 29.22
    assert parsed["metrics"]["idle"] == 52.86
    print(f"[PASS] end-to-end: metrics={parsed['metrics']}")

if __name__ == '__main__':
    test_captcha_parser()
    test_slurm_parser()
    test_full_mock_ssh_flow()
    print("\n✓ All tests passed.")
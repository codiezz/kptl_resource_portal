"""
captcha_parser.py

Parses the institute's ASCII keyboard-interactive captcha.

Expected input format (anywhere in a multi-line string):
    ( t | w | F | W | b | O | d | x )

Output:
    "twFWbOdx"

Design notes:
- Intentionally NOT a strategy class yet. One format, one parser.
  Add strategy dispatch only when a second format is confirmed.
- Parser is pure function — no side effects, easy to unit test.
- Strips whitespace from tokens to handle sloppy spacing.
"""

import re
from typing import Optional


# Matches the specific ASCII captcha format:
# ( token | token | token ... )
# Tokens are alphanumeric. Pipes are separators.
_CAPTCHA_PATTERN = re.compile(
    r'\(\s*((?:[A-Za-z0-9]+\s*\|\s*)*[A-Za-z0-9]+)\s*\)'
)


def parse_captcha(text: str) -> Optional[str]:
    """
    Extract captcha answer from a block of text.

    Args:
        text: Raw terminal output from SSH session (may be multi-line)

    Returns:
        The answer string (e.g. "twFWbOdx"), or None if no captcha found.

    Raises:
        Nothing. Caller is responsible for handling None (auth failure path).
    """
    match = _CAPTCHA_PATTERN.search(text)
    if not match:
        return None

    # Split on pipe, strip each token, join
    tokens = [t.strip() for t in match.group(1).split('|')]
    return ''.join(tokens)


def has_captcha(text: str) -> bool:
    """Quick check — does this text contain a captcha challenge?"""
    return _CAPTCHA_PATTERN.search(text) is not None


def extract_challenge_text(text: str) -> Optional[str]:
    """
    Return captcha challenge text for display in the UI.

    Does not solve the captcha — only extracts the challenge block so the
    user can read it and type the answer manually.
    """
    if not has_captcha(text):
        return None

    return text.strip()


# ---------------------------------------------------------------------------
# Self-test — run this file directly to verify parser works
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    test_cases = [
        (
            "Observe the picture below and answer the question listed\n"
            "\n"
            "( t | w | F | W | b | O | d | x )\n"
            "\n"
            "Type the string above:",
            "twFWbOdx"
        ),
        (
            "( A | B | C )",
            "ABC"
        ),
        (
            "( z | 3 | Q | r | 7 )\n"
            "Type the string above:",
            "z3Qr7"
        ),
        # Edge: extra whitespace inside tokens
        (
            "(  x  |  Y  |  9  )",
            "xY9"
        ),
        # Edge: no captcha present
        (
            "Password:",
            None
        ),
    ]

    all_passed = True
    for i, (input_text, expected) in enumerate(test_cases):
        result = parse_captcha(input_text)
        status = "PASS" if result == expected else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"[{status}] test {i+1}: expected={expected!r}, got={result!r}")

    print()
    print("All tests passed." if all_passed else "SOME TESTS FAILED.")
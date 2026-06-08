"""
login_session_store.py

In-memory store for pending SSH login sessions (live pexpect child processes).

The institute captcha must be answered on the same SSH connection, so we keep
the child alive between POST /login/start and POST /login/complete.
"""

import time
import uuid
from typing import Optional

SESSION_TTL_SECONDS = 300

_sessions: dict[str, tuple[object, float]] = {}


def store(pending_login) -> str:
    session_id = str(uuid.uuid4())
    _sessions[session_id] = (pending_login, time.time())
    return session_id


def pop(session_id: str):
    entry = _sessions.pop(session_id, None)
    if entry is None:
        return None

    pending_login, _created_at = entry
    return pending_login


def get(session_id: str) -> Optional[object]:
    entry = _sessions.get(session_id)
    if entry is None:
        return None

    pending_login, created_at = entry
    if time.time() - created_at > SESSION_TTL_SECONDS:
        pending_login.close()
        _sessions.pop(session_id, None)
        return None

    return pending_login


def cleanup_expired() -> None:
    now = time.time()
    expired = [
        session_id
        for session_id, (pending_login, created_at) in _sessions.items()
        if now - created_at > SESSION_TTL_SECONDS
    ]
    for session_id in expired:
        pending_login, _ = _sessions.pop(session_id)
        pending_login.close()

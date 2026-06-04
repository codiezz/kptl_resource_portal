"""
ssh_executor.py

Drives native OpenSSH (/usr/bin/ssh) via pexpect to handle the institute's
keyboard-interactive PAM authentication (ASCII captcha + password).

Output capture strategy:
    Send command → wait for next shell prompt → capture child.before
    This is more reliable than sentinel-based capture because:
    - The shell prompt is always present after any command
    - No risk of the sentinel appearing in command output
    - Works for multi-line output naturally

Session strategy: EPHEMERAL (connect → auth → run → disconnect)
Session reuse via SSH ControlMaster is a future optimization.
"""

import logging
import re
from dataclasses import dataclass

try:
    import pexpect
except ImportError:
    raise ImportError("pexpect is required: pip install pexpect")

from captcha_parser import parse_captcha

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SSHError(Exception):
    pass

class SSHAuthError(SSHError):
    pass

class SSHCommandError(SSHError):
    pass

class SSHTimeoutError(SSHError):
    pass

class SSHConnectionError(SSHError):
    pass


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class CommandResult:
    stdout: str
    host: str
    command: str


# ---------------------------------------------------------------------------
# Prompt patterns
# ---------------------------------------------------------------------------

P_CAPTCHA   = r'Type the string above:'
P_PASSWORD  = r'(?i)password\s*:'
P_SHELL     = r'\$\s*$'          # line ends with "$ "
P_HOSTKEY   = r'Are you sure you want to continue connecting'
P_DENIED    = r'(?i)permission denied'
P_REFUSED   = r'Connection refused'
P_EOF       = pexpect.EOF
P_TIMEOUT   = pexpect.TIMEOUT


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class SSHExecutor:

    def __init__(self, host: str, port: int = 22, timeout: int = 30,
                 ssh_binary: str = '/usr/bin/ssh'):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.ssh_binary = ssh_binary

    def run(self, username: str, password: str, command: str) -> CommandResult:
        args = [
            '-p', str(self.port),
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-F', '/dev/null',
            '-x', '-a',
            f'{username}@{self.host}',
        ]
        logger.debug(f"Spawning ssh to {self.host}")
        child = pexpect.spawn(
            self.ssh_binary, args,
            timeout=self.timeout,
            encoding='utf-8',
            codec_errors='replace',
        )
        try:
            return self._run_session(child, password, command)
        finally:
            if child.isalive():
                child.close(force=True)

    def _run_session(self, child, password: str, command: str) -> CommandResult:
        # Step 1: Handle optional host key acceptance
        idx = child.expect([P_HOSTKEY, P_CAPTCHA, P_PASSWORD, P_REFUSED, P_EOF, P_TIMEOUT])
        if idx == 3: raise SSHConnectionError(f"Connection refused to {self.host}")
        if idx == 4: raise SSHConnectionError(f"Connection to {self.host} dropped immediately")
        if idx == 5: raise SSHTimeoutError(f"No response from {self.host}")

        if idx == 0:  # host key prompt
            child.sendline('yes')
            idx = child.expect([P_CAPTCHA, P_PASSWORD, P_EOF, P_TIMEOUT])
            if idx == 2: raise SSHConnectionError("Connection dropped after host key")
            if idx == 3: raise SSHTimeoutError("No auth prompt after host key")
            idx_auth = idx  # 0=captcha, 1=password
        else:
            idx_auth = idx - 1  # shift: 1→0(captcha), 2→1(password)

        # Step 2: Captcha (if present)
        if idx_auth == 0:
            captcha_text = child.before
            answer = parse_captcha(captcha_text)
            if answer is None:
                raise SSHAuthError(f"Failed to parse captcha. Raw:\n{captcha_text!r}")
            logger.debug(f"Captcha answer: {answer}")
            child.sendline(answer)

            idx2 = child.expect([P_PASSWORD, P_DENIED, P_EOF, P_TIMEOUT])
            if idx2 == 1: raise SSHAuthError("Wrong captcha — permission denied")
            if idx2 == 2: raise SSHAuthError("Connection closed after captcha")
            if idx2 == 3: raise SSHTimeoutError("No password prompt after captcha")

        # Step 3: Password
        logger.debug("Sending password")
        child.sendline(password)

        # Step 4: Shell prompt
        idx3 = child.expect([P_SHELL, P_DENIED, P_EOF, P_TIMEOUT])
        if idx3 == 1: raise SSHAuthError("Wrong password — permission denied")
        if idx3 == 2: raise SSHAuthError("Connection closed after password")
        if idx3 == 3: raise SSHTimeoutError("Shell prompt not received")
        logger.debug("Authenticated — shell prompt received")

        # Step 5: Run command, wait for next shell prompt
        child.sendline(command)
        idx4 = child.expect([P_SHELL, P_EOF, P_TIMEOUT])
        if idx4 == 1: raise SSHCommandError("Connection dropped during command")
        if idx4 == 2: raise SSHTimeoutError(f"Command timed out after {self.timeout}s")

        raw = child.before  # everything between sendline and the next "$"

        # Strip the echoed command (first line)
        lines = raw.replace('\r\n', '\n').replace('\r', '\n').splitlines()
        if lines and command in lines[0]:
            lines = lines[1:]
        stdout = '\n'.join(lines).strip()

        # Step 6: Exit
        child.sendline('exit')
        child.expect([P_EOF, P_TIMEOUT])

        logger.debug(f"Command done. Output: {len(stdout)} chars")
        return CommandResult(stdout=stdout, host=self.host, command=command)


def run_hpc_command(host: str, username: str, password: str, command: str,
                    port: int = 22, timeout: int = 30) -> str:
    return SSHExecutor(host=host, port=port, timeout=timeout).run(
        username=username, password=password, command=command
    ).stdoutgit 
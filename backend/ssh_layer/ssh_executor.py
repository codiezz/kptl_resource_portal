
import logging
from dataclasses import dataclass
from typing import Optional

try:
    import pexpect
except ImportError:
    raise ImportError("pexpect is required: pip install pexpect")

from captcha_parser import extract_challenge_text, parse_captcha

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
# Result / login state
# ---------------------------------------------------------------------------

@dataclass
class CommandResult:
    stdout: str
    host: str
    command: str


@dataclass
class PendingLogin:
    """Live SSH session paused before or at the password step."""

    executor: "SSHExecutor"
    child: object
    username: str
    stage: str
    challenge_text: Optional[str] = None

    def complete(
        self,
        password: str,
        captcha_answer: Optional[str] = None,
        command: str = "echo connected",
    ) -> CommandResult:
        try:
            if self.stage == "captcha":
                if not captcha_answer:
                    raise SSHAuthError("Captcha answer is required")
                self.executor._submit_captcha(self.child, captcha_answer)

            return self.executor._finish_session(
                self.child,
                password=password,
                command=command,
            )
        finally:
            self.close()

    def close(self) -> None:
        if self.child.isalive():
            self.child.close(force=True)


# ---------------------------------------------------------------------------
# Prompt patterns
# ---------------------------------------------------------------------------

P_CAPTCHA = r"Type the string above:"
P_PASSWORD = r"(?i)password\s*:"
P_SHELL = r"\$\s*$"
P_HOSTKEY = r"Are you sure you want to continue connecting"
P_DENIED = r"(?i)permission denied"
P_REFUSED = r"Connection refused"
P_EOF = pexpect.EOF
P_TIMEOUT = pexpect.TIMEOUT


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class SSHExecutor:

    def __init__(
        self,
        host: str,
        port: int = 22,
        timeout: int = 30,
        ssh_binary: str = "/usr/bin/ssh",
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.ssh_binary = ssh_binary

    def run(self, username: str, password: str, command: str) -> CommandResult:
        child = self._spawn(username)
        try:
            stage, challenge_text = self._reach_auth_stage(child)
            if stage == "captcha":
                answer = parse_captcha(challenge_text or "")
                if answer is None:
                    raise SSHAuthError(
                        f"Failed to parse captcha. Raw:\n{challenge_text!r}"
                    )
                logger.debug(f"Auto captcha answer: {answer}")
                self._submit_captcha(child, answer)

            return self._finish_session(child, password=password, command=command)
        finally:
            if child.isalive():
                child.close(force=True)

    def begin_login(self, username: str) -> PendingLogin:
        """
        Start SSH with username@host and pause for manual captcha entry.

        Username is passed to the ssh binary (auto-filled). The returned
        PendingLogin must be completed with captcha_answer (manual) and
        password (auto-filled by the caller).
        """
        child = self._spawn(username)
        try:
            stage, challenge_text = self._reach_auth_stage(child)
            display_text = extract_challenge_text(challenge_text or "")

            return PendingLogin(
                executor=self,
                child=child,
                username=username,
                stage=stage,
                challenge_text=display_text,
            )
        except Exception:
            if child.isalive():
                child.close(force=True)
            raise

    def _spawn(self, username: str):
        args = [
            "-p",
            str(self.port),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-F",
            "/dev/null",
            "-x",
            "-a",
            f"{username}@{self.host}",
        ]
        logger.debug(f"Spawning ssh to {self.host}")
        return pexpect.spawn(
            self.ssh_binary,
            args,
            timeout=self.timeout,
            encoding="utf-8",
            codec_errors="replace",
        )

    def _reach_auth_stage(self, child) -> tuple[str, Optional[str]]:
        idx = child.expect(
            [P_HOSTKEY, P_CAPTCHA, P_PASSWORD, P_REFUSED, P_EOF, P_TIMEOUT]
        )
        if idx == 3:
            raise SSHConnectionError(f"Connection refused to {self.host}")
        if idx == 4:
            raise SSHConnectionError(
                f"Connection to {self.host} dropped immediately"
            )
        if idx == 5:
            raise SSHTimeoutError(f"No response from {self.host}")

        if idx == 0:
            child.sendline("yes")
            idx = child.expect([P_CAPTCHA, P_PASSWORD, P_EOF, P_TIMEOUT])
            if idx == 2:
                raise SSHConnectionError("Connection dropped after host key")
            if idx == 3:
                raise SSHTimeoutError("No auth prompt after host key")
            idx_auth = idx
        else:
            idx_auth = idx - 1

        if idx_auth == 0:
            challenge_text = (child.before or "") + (child.after or "")
            return "captcha", challenge_text

        return "password", None

    def _submit_captcha(self, child, captcha_answer: str) -> None:
        logger.debug("Sending manual captcha answer")
        child.sendline(captcha_answer)

        idx = child.expect([P_PASSWORD, P_DENIED, P_EOF, P_TIMEOUT])
        if idx == 1:
            raise SSHAuthError("Wrong captcha — permission denied")
        if idx == 2:
            raise SSHAuthError("Connection closed after captcha")
        if idx == 3:
            raise SSHTimeoutError("No password prompt after captcha")

    def _finish_session(
        self,
        child,
        password: str,
        command: str,
    ) -> CommandResult:
        logger.debug("Sending password")
        child.sendline(password)

        idx = child.expect([P_SHELL, P_DENIED, P_EOF, P_TIMEOUT])
        if idx == 1:
            raise SSHAuthError("Wrong password — permission denied")
        if idx == 2:
            raise SSHAuthError("Connection closed after password")
        if idx == 3:
            raise SSHTimeoutError("Shell prompt not received")
        logger.debug("Authenticated — shell prompt received")

        child.sendline(command)
        idx = child.expect([P_SHELL, P_EOF, P_TIMEOUT])
        if idx == 1:
            raise SSHCommandError("Connection dropped during command")
        if idx == 2:
            raise SSHTimeoutError(f"Command timed out after {self.timeout}s")

        raw = child.before
        lines = raw.replace("\r\n", "\n").replace("\r", "\n").splitlines()
        if lines and command in lines[0]:
            lines = lines[1:]
        stdout = "\n".join(lines).strip()

        child.sendline("exit")
        child.expect([P_EOF, P_TIMEOUT])

        logger.debug(f"Command done. Output: {len(stdout)} chars")
        return CommandResult(stdout=stdout, host=self.host, command=command)


def run_hpc_command(
    host: str,
    username: str,
    password: str,
    command: str,
    port: int = 22,
    timeout: int = 30,
) -> str:
    return SSHExecutor(host=host, port=port, timeout=timeout).run(
        username=username,
        password=password,
        command=command,
    ).stdout

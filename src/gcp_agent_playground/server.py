"""Lifecycle wrapper for a local mlx_lm.server subprocess."""
from __future__ import annotations

import atexit
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .profiles import Profile

LOG_DIR = Path("outputs/.server-logs")
READY_POLL_INTERVAL_S = 0.5
LOG_TAIL_LINES = 20


class ServerError(RuntimeError):
    """Raised when the local model server fails to start or stop cleanly."""


class MLXServer:
    def __init__(self, profile: Profile):
        self.profile = profile
        self._proc: subprocess.Popen | None = None
        self._log_path: Path | None = None
        self._stopped = False

    # ---- public API -----------------------------------------------------

    def start(self, ready_timeout_s: float = 120.0) -> None:
        if self._already_serving():
            raise ServerError(
                f"Port {self.profile.port} is already serving a model. "
                f"Stop the existing server or change the port in your profile."
            )

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        self._log_path = LOG_DIR / f"{ts}.log"
        log_file = self._log_path.open("w")

        try:
            self._proc = subprocess.Popen(
                [
                    "mlx_lm.server",
                    "--model", self.profile.model,
                    "--host", self.profile.host,
                    "--port", str(self.profile.port),
                    "--use-default-chat-template",
                ],
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
        except FileNotFoundError as e:
            raise ServerError(
                "mlx_lm.server not found on PATH. Did you 'uv sync'? "
                "Try: uv run mlx_lm.server --help"
            ) from e

        atexit.register(self.stop)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self._wait_ready(ready_timeout_s)

    def stop(self, term_grace_s: float = 5.0) -> None:
        if self._stopped or self._proc is None:
            return
        self._stopped = True
        proc = self._proc
        if proc.poll() is not None:
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=term_grace_s)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        except ProcessLookupError:
            pass

    def is_ready(self) -> bool:
        try:
            r = httpx.get(f"{self.profile.base_url}/models", timeout=2.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    # ---- context manager -----------------------------------------------

    def __enter__(self) -> "MLXServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    # ---- internals -----------------------------------------------------

    def _already_serving(self) -> bool:
        return self.is_ready()

    def _wait_ready(self, timeout_s: float) -> None:
        assert self._proc is not None
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                self._raise_with_log_tail(
                    f"mlx_lm.server exited with code {self._proc.returncode} before becoming ready."
                )
            if self.is_ready():
                return
            time.sleep(READY_POLL_INTERVAL_S)
        self.stop()
        self._raise_with_log_tail(
            f"mlx_lm.server did not become ready within {timeout_s:.0f}s."
        )

    def _raise_with_log_tail(self, message: str) -> None:
        tail = ""
        if self._log_path and self._log_path.exists():
            lines = self._log_path.read_text().splitlines()[-LOG_TAIL_LINES:]
            tail = "\n".join(lines)
        raise ServerError(f"{message}\n\n--- last {LOG_TAIL_LINES} lines of {self._log_path} ---\n{tail}")

    def _signal_handler(self, signum, frame) -> None:
        self.stop()
        # Re-raise the default behavior so the process actually exits.
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

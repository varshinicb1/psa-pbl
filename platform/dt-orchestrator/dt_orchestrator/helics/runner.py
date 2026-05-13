from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class HelicsUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class HelicsConfig:
    """
    Minimal configuration for a HELICS federation (PoC scaffolding).
    """

    federation_json: Path
    broker_args: str = "--loglevel=warning"


class HelicsFederationRunner:
    """
    HELICS runner scaffolding.

    This intentionally does not hard-depend on the Python helics bindings yet.
    It can (optionally) start a broker if `helics_broker` is installed.
    """

    def __init__(self, config: HelicsConfig) -> None:
        self.config = config
        self._broker_exe: Optional[str] = shutil.which("helics_broker")
        self._proc: Optional[subprocess.Popen] = None

    def available(self) -> bool:
        return self._broker_exe is not None

    def validate_config(self) -> None:
        if not self.config.federation_json.exists():
            raise FileNotFoundError(str(self.config.federation_json))
        _ = json.loads(self.config.federation_json.read_text(encoding="utf-8"))

    def start_broker(self) -> None:
        """
        Start a HELICS broker process (if available). Non-blocking.
        """
        if not self._broker_exe:
            raise HelicsUnavailable(
                "helics_broker not found on PATH. Install HELICS to enable federated co-simulation."
            )
        self.validate_config()
        # Minimal broker; in real use we would pass core type, federate count, etc.
        cmd = [self._broker_exe] + self.config.broker_args.split()
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def stop_broker(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
        self._proc = None


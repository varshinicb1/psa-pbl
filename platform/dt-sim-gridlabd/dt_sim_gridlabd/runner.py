from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class GridlabdUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class GridlabdRunResult:
    exit_code: int
    stdout: str
    stderr: str


class GridlabdRunner:
    """
    Skeleton runner for GridLAB-D CLI execution.

    Next iterations:
    - standardized output extraction (JSON/tape parsing)
    - parameter injection for scenario generation
    - HELICS federate mode integration
    """

    def __init__(self, *, gridlabd_exe: Optional[str] = None) -> None:
        self.gridlabd_exe = gridlabd_exe or shutil.which("gridlabd")
        if not self.gridlabd_exe:
            raise GridlabdUnavailable("gridlabd executable not found on PATH. Build/install GridLAB-D first.")

    def run(self, glm_path: Path, *, cwd: Optional[Path] = None, timeout_s: int = 120) -> GridlabdRunResult:
        proc = subprocess.run(
            [self.gridlabd_exe, str(glm_path)],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return GridlabdRunResult(exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


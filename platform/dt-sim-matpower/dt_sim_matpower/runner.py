from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


class MatpowerBackendUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class MatpowerPFResult:
    success: bool
    bus: Dict[str, Any]
    gen: Dict[str, Any]
    branch: Dict[str, Any]


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


class MatpowerRunner:
    """
    Minimal MATPOWER runner intended for cross-validation/benchmarking.

    Backends:
    - local octave (preferred)
    - docker image (optional; requires daemon)
    """

    def __init__(self, *, matpower_root: Path) -> None:
        self.matpower_root = matpower_root

    def backend_available(self) -> bool:
        if _which("octave"):
            return True
        if _which("docker"):
            # Docker client present does not guarantee daemon; check quickly
            try:
                subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                return True
            except Exception:
                return False
        return False

    def run_pf_case(self, case_name: str = "case14") -> MatpowerPFResult:
        """
        Run power flow for a built-in MATPOWER case (e.g., case14, case118).
        """
        if not self.backend_available():
            raise MatpowerBackendUnavailable(
                "No MATPOWER backend available. Install GNU Octave (octave on PATH) or run Docker daemon with the MATPOWER image."
            )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_json = tmp_path / "pf_result.json"
            script_path = tmp_path / "run_pf_to_json.m"
            script_path.write_text(self._octave_script(), encoding="utf-8")

            if _which("octave"):
                # Use local Octave and point it at MATPOWER root
                cmd = [
                    "octave",
                    "-qf",
                    str(script_path),
                    str(self.matpower_root),
                    case_name,
                    str(out_json),
                ]
                subprocess.run(cmd, check=True)
            else:
                # Docker fallback (requires daemon)
                # Mount MATPOWER and temp dir into container and execute Octave there.
                # Note: This requires Docker Desktop/daemon to be running.
                cmd = [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{self.matpower_root.as_posix()}:/matpower",
                    "-v",
                    f"{tmp_path.as_posix()}:/work",
                    "matpower/matpower",
                    "octave",
                    "-qf",
                    "/work/run_pf_to_json.m",
                    "/matpower",
                    case_name,
                    "/work/pf_result.json",
                ]
                subprocess.run(cmd, check=True)

            data = json.loads(out_json.read_text(encoding="utf-8"))
            return MatpowerPFResult(
                success=bool(data.get("success", False)),
                bus=data.get("bus", {}),
                gen=data.get("gen", {}),
                branch=data.get("branch", {}),
            )

    @staticmethod
    def _octave_script() -> str:
        """
        Octave script (inline) to run MATPOWER PF and write minimal JSON results.
        Args:
          argv1: matpower_root
          argv2: case_name (e.g. case14)
          argv3: out_json path
        """
        return r"""
function main()
  args = argv();
  if numel(args) < 3
    error("Usage: run_pf_to_json.m <matpower_root> <case_name> <out_json>");
  end
  mp_root = args{1};
  case_name = args{2};
  out_json = args{3};

  addpath(mp_root);

  % Load case and run PF
  mpc = feval(case_name);
  results = runpf(mpc, mpoption('verbose', 0, 'out.all', 0));
  success = results.success;

  % Extract a minimal subset:
  % bus columns: BUS_I, VM, VA (indices per MATPOWER constants)
  define_constants;
  bus_i = results.bus(:, BUS_I);
  vm = results.bus(:, VM);
  va = results.bus(:, VA);

  % Write JSON (jsonencode available in modern Octave)
  payload = struct();
  payload.success = success;
  payload.bus = struct('bus_i', bus_i, 'vm', vm, 'va', va);
  payload.gen = struct();
  payload.branch = struct();

  fid = fopen(out_json, 'w');
  if fid < 0
    error("Could not open out_json for writing");
  end
  fprintf(fid, "%s", jsonencode(payload));
  fclose(fid);
end

main();
"""


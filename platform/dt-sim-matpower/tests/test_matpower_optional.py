import pathlib
import sys

import pytest


def _bootstrap_paths() -> None:
    repo_root = pathlib.Path(__file__).resolve().parents[3]  # .../pbl
    sys.path.insert(0, str(repo_root / "platform" / "dt-sim-matpower"))


_bootstrap_paths()


from dt_sim_matpower.runner import MatpowerBackendUnavailable, MatpowerRunner  # noqa: E402


def test_matpower_backend_optional():
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    matpower_root = repo_root / "upstreams" / "matpower"
    runner = MatpowerRunner(matpower_root=matpower_root)

    if not runner.backend_available():
        pytest.skip("MATPOWER backend not available (needs Octave or Docker daemon).")

    res = runner.run_pf_case("case14")
    assert res.success is True
    assert len(res.bus.get("vm", [])) > 0


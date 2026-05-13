import pathlib
import sys

import pytest


def _bootstrap_paths() -> None:
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root / "platform" / "dt-sim-gridlabd"))


_bootstrap_paths()


from dt_sim_gridlabd.runner import GridlabdRunner, GridlabdUnavailable  # noqa: E402


def test_gridlabd_backend_optional():
    try:
        _ = GridlabdRunner()
    except GridlabdUnavailable:
        pytest.skip("GridLAB-D executable not available in this environment.")


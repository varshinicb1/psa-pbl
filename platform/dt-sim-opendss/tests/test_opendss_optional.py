import pathlib
import sys

import pytest


def _bootstrap_paths() -> None:
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root / "platform" / "dt-contracts" / "python" / "src"))
    sys.path.insert(0, str(repo_root / "platform" / "dt-sim-opendss"))


_bootstrap_paths()


from dt_sim_opendss.adapter import OpenDSSAdapter, OpenDSSBackendUnavailable, OpenDSSConfig  # noqa: E402


def test_opendss_backend_optional():
    try:
        _ = OpenDSSAdapter(OpenDSSConfig(master_dss_path="dummy.dss"))
    except OpenDSSBackendUnavailable:
        pytest.skip("OpenDSSDirect.py backend not available in this environment.")


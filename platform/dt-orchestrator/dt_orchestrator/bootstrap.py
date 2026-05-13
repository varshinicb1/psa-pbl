from __future__ import annotations

import pathlib
import sys


def bootstrap_local_paths() -> None:
    """
    Make the monorepo-style PoC runnable without packaging every module.
    """
    repo_root = pathlib.Path(__file__).resolve().parents[3]  # .../pbl
    sys.path.insert(0, str(repo_root / "platform" / "dt-contracts" / "python" / "src"))
    sys.path.insert(0, str(repo_root / "platform" / "dt-sim-pandapower"))


"""
Bootstrap module for development/research environments.

Handles path setup for monorepo-style structure without requiring packaging.
Uses environment-based path resolution for robustness.
"""

from __future__ import annotations

import logging
import pathlib
import sys
from typing import Optional

logger = logging.getLogger(__name__)


def bootstrap_local_paths(repo_root: Optional[pathlib.Path] = None) -> pathlib.Path:
    """
    Configure Python path for monorepo-style local development.

    Adds platform modules to sys.path without requiring package installation.

    Args:
        repo_root: Override repo root path (for testing); auto-detected if None

    Returns:
        Detected repo root path

    Raises:
        RuntimeError: If repo structure is invalid
    """
    # Detect repo root
    if repo_root is None:
        # Start from this file and walk up until we find "pbl" directory
        current = pathlib.Path(__file__).resolve()
        max_depth = 10
        depth = 0

        while current != current.parent and depth < max_depth:
            if current.name == "pbl" and (current / "platform").exists():
                repo_root = current
                break
            current = current.parent
            depth += 1

        if repo_root is None:
            raise RuntimeError(
                "Could not detect repo root. Ensure you're running from within pbl/ directory or provide repo_root."
            )

    repo_root = repo_root.resolve()
    logger.debug(f"Bootstrap repo_root: {repo_root}")

    # Validate structure
    platform_dir = repo_root / "platform"
    if not platform_dir.exists():
        raise RuntimeError(f"Invalid repo structure: platform/ not found at {repo_root}")

    # Add modules to path
    paths_to_add = [
        platform_dir / "dt-contracts" / "python" / "src",
        platform_dir / "dt-sim-pandapower",
        platform_dir / "dt-orchestrator",
        platform_dir / "dt-ml",
        platform_dir / "dt-scada-protocols" / "src",
        platform_dir / "dt-compliance" / "src",
        platform_dir / "dt-cim" / "src",
        platform_dir / "dt-bescom" / "src",
        platform_dir / "dt_security",
        platform_dir / "dt-dataset-factory",
        platform_dir / "dt-restoration-agent",
    ]

    for path in paths_to_add:
        if path.exists():
            sys.path.insert(0, str(path))
            logger.debug(f"Added to sys.path: {path}")
        else:
            logger.warning(f"Module path not found: {path}")

    logger.info(f"Bootstrap complete - loaded {len([p for p in paths_to_add if p.exists()])} modules")
    return repo_root


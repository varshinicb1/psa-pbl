"""
Production-grade GridLAB-D runner for distribution system simulation.

Supports:
- CLI execution of GLM models
- JSON output parsing
- Parameter injection for scenario generation
- Integration with HELICS for co-simulation
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from dt_contracts.models import (
    ExternalRef,
    GridEdge,
    GridGraphSnapshot,
    GridNode,
    SCHEMA_VERSION,
)
from dt_contracts.utils import utc_now_iso, stable_hash


class GridlabdUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class GridlabdRunResult:
    exit_code: int
    stdout: str
    stderr: str
    execution_time_ms: float = 0.0


@dataclass
class GridlabdConfig:
    grid_id: str = "metro-grid"
    solver_method: str = "NR"
    maximum_iterations: int = 100
    default_timestep_s: int = 60


class GridlabdRunner:
    """
    Production-grade GridLAB-D runner for distribution grid digital twins.

    Features:
    - GLM model execution with timeout
    - JSON/CSV output parsing
    - Parameter injection via environment variables
    - Player file generation for deterministic scenarios
    - Result mapping to canonical GridGraphSnapshot
    """

    def __init__(
        self,
        *,
        gridlabd_exe: Optional[str] = None,
        config: Optional[GridlabdConfig] = None,
    ) -> None:
        self.gridlabd_exe = gridlabd_exe or shutil.which("gridlabd")
        if not self.gridlabd_exe:
            raise GridlabdUnavailable(
                "gridlabd not found on PATH. Build/install GridLAB-D first."
            )
        self.config = config or GridlabdConfig()

    def run(
        self,
        glm_path: Path,
        *,
        cwd: Optional[Path] = None,
        timeout_s: int = 120,
        params: Optional[Dict[str, str]] = None,
    ) -> GridlabdRunResult:
        start = time.perf_counter()
        env = os.environ.copy()
        if params:
            env.update(params)

        proc = subprocess.run(
            [self.gridlabd_exe, str(glm_path)],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=env,
        )
        elapsed = (time.perf_counter() - start) * 1000
        return GridlabdRunResult(
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            execution_time_ms=elapsed,
        )

    def run_with_player(
        self,
        glm_template: str,
        player_data: Dict[str, List[float]],
        *,
        timesteps: int = 10,
        timeout_s: int = 120,
    ) -> GridlabdRunResult:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            glm_path = tmp_path / "model.glm"
            glm_path.write_text(glm_template, encoding="utf-8")

            for name, values in player_data.items():
                player_path = tmp_path / f"{name}.csv"
                with open(player_path, "w", newline="") as f:
                    writer = csv.writer(f)
                    for i, v in enumerate(values):
                        writer.writerow([i * self.config.default_timestep_s, v])

            return self.run(glm_path, cwd=tmp_path, timeout_s=timeout_s)

    def parse_metrics(self, result: GridlabdRunResult) -> Dict[str, Any]:
        metrics = {}
        for line in result.stdout.split("\n"):
            match = re.match(
                r'(\w[\w.]*)\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)?', line
            )
            if match:
                key = match.group(1)
                try:
                    metrics[key] = float(match.group(2))
                except ValueError:
                    metrics[key] = match.group(2)
        return metrics

    def parse_json_output(self, result: GridlabdRunResult) -> List[Dict[str, Any]]:
        objects = []
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    obj = json.loads(line)
                    objects.append(obj)
                except json.JSONDecodeError:
                    pass
        return objects

    def to_snapshot(
        self,
        result: GridlabdRunResult,
        *,
        t: Optional[str] = None,
    ) -> GridGraphSnapshot:
        t = t or utc_now_iso()
        metrics = self.parse_metrics(result)
        objects = self.parse_json_output(result)

        nodes: List[GridNode] = []
        edges: List[GridEdge] = []
        bus_map: Dict[str, str] = {}

        for i, obj in enumerate(objects):
            obj_class = obj.get("class", obj.get("object", "unknown"))
            name = obj.get("name", obj.get("id", f"obj_{i}"))

            if obj_class.lower() in ("node", "bus", "load", "capacitor"):
                nid = f"{self.config.grid_id}/gridlabd/{obj_class}/{name}"
                bus_map[name] = nid

                vm = obj.get("voltage_A", obj.get("voltage_12", 0))
                try:
                    vm = float(vm) if vm is not None else 0.0
                except (ValueError, TypeError):
                    vm = 0.0

                nodes.append(
                    GridNode(
                        id=nid,
                        type="Bus",
                        static={"class": obj_class, "name": name},
                        dynamic={"vm_pu": vm / 120.0 if vm > 100 else vm},
                        external_refs=[
                            ExternalRef(
                                engine="gridlabd",
                                object_type=obj_class,
                                object_name=name,
                            )
                        ],
                    )
                )

        for i, obj in enumerate(objects):
            obj_class = obj.get("class", obj.get("object", "unknown"))
            name = obj.get("name", obj.get("id", f"obj_{i}"))

            if obj_class.lower() in ("meter", "load", "triplex_meter"):
                node_id = bus_map.get(
                    name,
                    f"{self.config.grid_id}/gridlabd/bus/{name}",
                )
                parent = obj.get("parent", obj.get("billing_meter", ""))
                if parent:
                    parent_id = bus_map.get(
                        parent,
                        f"{self.config.grid_id}/gridlabd/bus/{parent}",
                    )
                    edges.append(
                        GridEdge(
                            id=f"{self.config.grid_id}/gridlabd/edge/{name}_to_{parent}",
                            type="Line",
                            source=parent_id,
                            target=node_id,
                            static={"class": obj_class},
                            dynamic={},
                        )
                    )

        if not edges and len(nodes) >= 2:
            for j in range(len(nodes) - 1):
                edges.append(
                    GridEdge(
                        id=f"{self.config.grid_id}/gridlabd/edge/auto_{j}",
                        type="Line",
                        source=nodes[j].id,
                        target=nodes[j + 1].id,
                        static={"auto_generated": True},
                        dynamic={},
                    )
                )

        topo_material = {
            "grid_id": self.config.grid_id,
            "engine": "gridlabd",
            "bus_count": len(nodes),
            "edge_count": len(edges),
        }
        topo_hash = stable_hash(topo_material)

        return GridGraphSnapshot(
            schema_version=SCHEMA_VERSION,
            t=t,
            topology_hash=topo_hash,
            topology_version=0,
            metadata={
                "engine_projection": "gridlabd",
                "grid_id": self.config.grid_id,
                "exit_code": result.exit_code,
            },
            nodes=nodes,
            edges=edges,
        )

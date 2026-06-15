"""
Dataset generation: IEEE-14 voltage anomaly scenarios.

Generates synthetic grids under random conditions with labeled voltage anomalies.
Output: CSV/Parquet timeseries for ML training.
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys
from typing import Optional

import pandas as pd

# Setup logging
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent / "dt-contracts"))
from logging_config import setup_logging, get_logger

setup_logging(log_level="INFO")
logger = get_logger(__name__)

# Voltage bounds
VOLTAGE_LOWER_BOUND = 0.95
VOLTAGE_UPPER_BOUND = 1.05


def bootstrap_paths(repo_root: Optional[pathlib.Path] = None) -> pathlib.Path:
    """Bootstrap sys.path for monorepo imports."""
    if repo_root is None:
        # Find repo root
        current = pathlib.Path(__file__).resolve()
        while current != current.parent:
            if current.name == "pbl" and (current / "platform").exists():
                repo_root = current
                break
            current = current.parent

    if repo_root is None:
        raise RuntimeError("Could not find repo root")

    repo_root = repo_root.resolve()
    logger.debug(f"Bootstrapping from repo_root: {repo_root}")

    paths = [
        repo_root / "platform" / "dt-contracts" / "python" / "src",
        repo_root / "platform" / "dt-sim-pandapower",
        repo_root / "platform" / "dt-orchestrator",
    ]

    for path in paths:
        if path.exists():
            sys.path.insert(0, str(path))

    return repo_root


def main() -> None:
    """Generate dataset."""
    ap = argparse.ArgumentParser(description="Generate IEEE-14 voltage anomaly dataset")
    ap.add_argument("--scenarios", type=int, default=20, help="Number of scenarios")
    ap.add_argument("--ticks", type=int, default=60, help="Ticks per scenario")
    ap.add_argument(
        "--outdir", type=str, default="platform/datasets/ieee14_voltage_anomaly", help="Output directory"
    )
    args = ap.parse_args()

    logger.info(f"Generating dataset: scenarios={args.scenarios} ticks={args.ticks}")

    try:
        repo_root = bootstrap_paths()
        from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner
        from dt_contracts.utils import utc_now_iso
    except ImportError as exc:
        logger.error(f"Import failed: {exc}")
        sys.exit(1)

    outdir = (repo_root / args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {outdir}")

    rows = []
    labels = []
    total_ticks = 0
    anomalies_found = 0

    try:
        for s in range(args.scenarios):
            try:
                logger.debug(f"Scenario {s + 1}/{args.scenarios}")
                runner = RealtimeTickRunner(grid_id=f"ds/ieee14/scenario_{s}", seed=1000 + s)

                for k in range(args.ticks):
                    out = runner.run_one_tick()
                    t = out.snapshot.t
                    total_ticks += 1

                    worst_dev = 0.0
                    worst_bus: Optional[str] = None

                    for n in out.snapshot.nodes:
                        vm = n.dynamic.get("vm_pu")
                        if vm is None:
                            continue

                        try:
                            vm_val = float(vm)
                            dev = max(0.0, vm_val - VOLTAGE_UPPER_BOUND, VOLTAGE_LOWER_BOUND - vm_val)
                        except (ValueError, TypeError):
                            logger.debug(f"Invalid vm_pu for node {n.id}: {vm}")
                            continue

                        if dev > worst_dev:
                            worst_dev = dev
                            worst_bus = n.id

                        rows.append(
                            {
                                "scenario_id": s,
                                "tick": k,
                                "t": t,
                                "node_id": n.id,
                                "vm_pu": vm_val,
                                "va_degree": float(n.dynamic.get("va_degree", 0.0)),
                                "dev_out_of_bounds": float(dev),
                            }
                        )

                    has_anomaly = bool(worst_dev > 0)
                    if has_anomaly:
                        anomalies_found += 1

                    labels.append(
                        {
                            "scenario_id": s,
                            "tick": k,
                            "t": t,
                            "label_voltage_anomaly": has_anomaly,
                            "worst_dev": float(worst_dev),
                            "worst_node_id": worst_bus,
                        }
                    )

            except Exception as exc:
                logger.error(f"Scenario {s} failed: {exc}")
                raise

        # Write CSV
        df = pd.DataFrame(rows)
        df_labels = pd.DataFrame(labels)

        csv_path = outdir / "node_timeseries.csv"
        df.to_csv(csv_path, index=False)
        logger.info(f"Wrote {len(df)} rows to {csv_path.name}")

        labels_path = outdir / "labels.csv"
        df_labels.to_csv(labels_path, index=False)
        logger.info(f"Wrote {len(df_labels)} labels to {labels_path.name}")

        # Optional parquet format
        try:
            import pyarrow  # noqa: F401

            df.to_parquet(outdir / "node_timeseries.parquet", index=False)
            df_labels.to_parquet(outdir / "labels.parquet", index=False)
            logger.info("Wrote Parquet formats")
        except ImportError:
            logger.debug("PyArrow not available - skipping Parquet output")
        except Exception as exc:
            logger.warning(f"Parquet export failed: {exc}")

        # Write metadata
        metadata = f"""generated_at={utc_now_iso()}
scenarios={args.scenarios}
ticks_per_scenario={args.ticks}
total_ticks={total_ticks}
anomalies_found={anomalies_found}
anomaly_rate={100.0 * anomalies_found / len(df_labels):.1f}%
voltage_bounds=[{VOLTAGE_LOWER_BOUND}, {VOLTAGE_UPPER_BOUND}]
"""
        (outdir / "_DONE.txt").write_text(metadata, encoding="utf-8")
        logger.info(f"Dataset generation complete - anomaly_rate={100.0 * anomalies_found / len(df_labels):.1f}%")
        print(f"✓ Wrote dataset to: {outdir}")

    except Exception as exc:
        logger.error(f"Dataset generation failed: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()


from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import datetime, timezone

import pandas as pd


def _bootstrap_paths(repo_root: pathlib.Path) -> None:
    sys.path.insert(0, str(repo_root / "platform" / "dt-contracts" / "python" / "src"))
    sys.path.insert(0, str(repo_root / "platform" / "dt-sim-pandapower"))
    sys.path.insert(0, str(repo_root / "platform" / "dt-orchestrator"))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=int, default=20)
    ap.add_argument("--ticks", type=int, default=60)
    ap.add_argument("--outdir", type=str, default="platform/datasets/ieee14_voltage_anomaly")
    args = ap.parse_args()

    repo_root = pathlib.Path(__file__).resolve().parents[2]  # .../pbl
    _bootstrap_paths(repo_root)

    from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner  # noqa: E402

    outdir = (repo_root / args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    rows = []
    labels = []

    for s in range(args.scenarios):
        runner = RealtimeTickRunner(grid_id=f"ds/ieee14/scenario_{s}", seed=1000 + s)
        for k in range(args.ticks):
            out = runner.run_one_tick()
            t = out.snapshot.t

            worst_dev = 0.0
            worst_bus = None
            for n in out.snapshot.nodes:
                vm = n.dynamic.get("vm_pu")
                if vm is None:
                    continue
                dev = max(0.0, float(vm) - 1.05, 0.95 - float(vm))
                if dev > worst_dev:
                    worst_dev = dev
                    worst_bus = n.id

                rows.append(
                    {
                        "scenario_id": s,
                        "tick": k,
                        "t": t,
                        "node_id": n.id,
                        "vm_pu": float(vm),
                        "va_degree": float(n.dynamic.get("va_degree", 0.0)),
                        "dev_out_of_bounds": float(dev),
                    }
                )

            labels.append(
                {
                    "scenario_id": s,
                    "tick": k,
                    "t": t,
                    "label_voltage_anomaly": bool(worst_dev > 0),
                    "worst_dev": float(worst_dev),
                    "worst_node_id": worst_bus,
                }
            )

    df = pd.DataFrame(rows)
    df_labels = pd.DataFrame(labels)

    df.to_csv(outdir / "node_timeseries.csv", index=False)
    df_labels.to_csv(outdir / "labels.csv", index=False)

    # Optional parquet if pyarrow is installed
    try:
        import pyarrow  # noqa: F401

        df.to_parquet(outdir / "node_timeseries.parquet", index=False)
        df_labels.to_parquet(outdir / "labels.parquet", index=False)
    except Exception:
        pass

    (outdir / "_DONE.txt").write_text(f"generated_at={_utc_now_iso()}\n", encoding="utf-8")
    print(f"Wrote dataset to: {outdir}")


if __name__ == "__main__":
    main()


from __future__ import annotations

import pathlib
import sys


def _bootstrap(repo_root: pathlib.Path) -> None:
    sys.path.insert(0, str(repo_root / "platform" / "dt-contracts" / "python" / "src"))
    sys.path.insert(0, str(repo_root / "platform" / "dt-ml"))


def main() -> None:
    repo_root = pathlib.Path(__file__).resolve().parents[2]  # .../pbl
    _bootstrap(repo_root)

    from dt_ml.data.loaders import load_ieee14_voltage_anomaly_dataset  # noqa: E402

    ds_dir = repo_root / "platform" / "datasets" / "ieee14_voltage_anomaly"
    ds = load_ieee14_voltage_anomaly_dataset(ds_dir)
    print("node_timeseries rows:", len(ds.node_timeseries))
    print("labels rows:", len(ds.labels))
    print(ds.labels.head(3).to_string(index=False))


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import time

from dt_orchestrator.bootstrap import bootstrap_local_paths

bootstrap_local_paths()

from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner  # noqa: E402


def main() -> None:
    runner = RealtimeTickRunner()
    for i in range(5):
        out = runner.run_one_tick()
        print(f"[tick {i}] solved={out.metrics['solved']} topology_hash={out.snapshot.topology_hash[:8]}")
        if out.explanation:
            print("  explanation:", json.dumps(out.explanation.model_dump(), indent=2)[:500])
        time.sleep(0.5)


if __name__ == "__main__":
    main()


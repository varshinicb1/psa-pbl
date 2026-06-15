"""
Demo run: IEEE-14 bus system with synthetic load perturbations.

Runs 5 ticks of near-real-time simulation and reports anomalies.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

# Setup paths and logging
sys.path.insert(0, str(Path(__file__).parent))

from dt_contracts.logging_config import setup_logging, get_logger

setup_logging(log_level="INFO")
logger = get_logger(__name__)

from dt_orchestrator.bootstrap import bootstrap_local_paths
from dt_contracts.exceptions import TickExecutionError

try:
    bootstrap_local_paths()
except RuntimeError as e:
    logger.error(f"Bootstrap failed: {e}")
    sys.exit(1)

from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner


def main() -> None:
    """Run demo simulation."""
    logger.info("Starting Grid Digital Twin Demo")
    logger.info("Simulating IEEE-14 with synthetic load perturbations")

    try:
        runner = RealtimeTickRunner()
        logger.info("Runner initialized successfully")

        for tick_num in range(5):
            try:
                logger.debug(f"Executing tick {tick_num}")
                out = runner.run_one_tick()

                # Log tick result
                solved = out.metrics.get("solved", False)
                status = "✓ converged" if solved else "✗ no convergence"
                logger.info(
                    f"Tick {tick_num}: {status} | topology_hash={out.snapshot.topology_hash[:8]}"
                )

                # Report anomalies if detected
                if out.explanation:
                    logger.warning(
                        f"Anomaly detected: {out.explanation.event_type}"
                    )
                    logger.debug(
                        f"Details: {json.dumps(out.explanation.model_dump(), indent=2)[:200]}"
                    )

                time.sleep(0.5)

            except TickExecutionError as e:
                logger.error(f"Tick {tick_num} failed: {e}")
                raise

        logger.info("Demo completed successfully - 5 ticks executed")

    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()


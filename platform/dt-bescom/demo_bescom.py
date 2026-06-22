"""
BESCOM Bangalore Grid — Accurate Simulation Demo.

Builds the real BESCOM network model, runs power flow with
time-of-day load profiles, and validates results.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bescom_demo")

sys.path.insert(0, "src")


def main():
    logger.info("=" * 60)
    logger.info("BESCOM Bangalore Grid - Accurate Simulation")
    logger.info("=" * 60)

    # --- Network Description ---
    from dt_bescom.network_model import build_bescom_network, describe_network

    logger.info("Building BESCOM network model...")
    net = build_bescom_network()

    logger.info("\n" + describe_network(net))

    # --- Run power flow at peak hour (10 AM) ---
    from dt_bescom.load_profiles import BESCOMLoadProfile, get_bangalore_daily_load_curve
    import pandapower as pp

    peak_time = datetime(2025, 6, 15, 10, 0, tzinfo=timezone.utc)
    profile = BESCOMLoadProfile()
    load_factor = profile.get_hourly_factor(peak_time)
    net.load.scaling = load_factor

    logger.info(f"\nRunning power flow at {peak_time.isoformat()}")
    logger.info(f"  Load factor: {load_factor:.3f}")
    logger.info(f"  Total connected load: {net.load.p_mw.sum() * load_factor:.1f} MW")

    pp.runpp(net, numba=False, tolerance_mva=1e-8)
    logger.info(f"  Converged: {net.converged}")

    if net.converged:
        # --- Results summary ---
        vm = net.res_bus["vm_pu"]
        va = net.res_bus["va_degree"]
        loading = net.res_line["loading_percent"]

        logger.info(f"\nResults:")
        logger.info(f"  Voltage range: {vm.min():.4f} - {vm.max():.4f} p.u.")
        logger.info(f"  Angle range: {va.min():.2f} - {va.max():.2f} deg")
        logger.info(f"  Line loading range: {loading.min():.1f} - {loading.max():.1f} %")
        logger.info(f"  Total losses: {net.res_line.pl_mw.sum():.2f} MW")

        # Voltage violations
        violations = net.res_bus[(vm < 0.95) | (vm > 1.05)]
        if len(violations) > 0:
            logger.warning(f"\n  ⚠ Voltage violations: {len(violations)} buses")
            for idx in violations.index:
                name = net.bus.at[idx, "name"]
                logger.warning(f"    {name}: {vm[idx]:.4f} p.u.")
        else:
            logger.info(f"\n  ✓ All voltages in band (0.95-1.05 p.u.)")

        # Line overloads
        overloads = net.res_line[loading > 90]
        if len(overloads) > 0:
            logger.warning(f"\n  ⚠ Line overloads: {len(overloads)} lines")
            for idx in overloads.index:
                name = net.line.at[idx, "name"]
                logger.warning(f"    {name}: {loading[idx]:.1f}%")
        else:
            logger.info(f"  ✓ No line overloads (>90%)")

    # --- Run at different times of day ---
    logger.info(f"\n--- Time-of-day simulation ---")
    for hour in [0, 6, 10, 14, 18, 22]:
        t = datetime(2025, 6, 15, hour, 0, tzinfo=timezone.utc)
        lf = profile.get_hourly_factor(t)
        net.load.scaling = lf
        try:
            pp.runpp(net, numba=False, tolerance_mva=1e-8)
            total_load = net.res_load.p_mw.sum()
            losses = net.res_line.pl_mw.sum()
            logger.info(f"  {hour:02d}:00 — load={total_load:7.1f} MW  losses={losses:5.2f} MW  vm={vm.min():.4f}-{vm.max():.4f} p.u.")
        except pp.powerflow.LoadflowNotConverged:
            logger.warning(f"  {hour:02d}:00 — DID NOT CONVERGE")

    # --- CIM Integration ---
    logger.info(f"\n--- CIM / GridGraph Integration ---")
    from dt_bescom.simulation import BESCOMSimulator

    sim = BESCOMSimulator()
    snap = sim.to_grid_graph_snapshot(tick_count=1)
    logger.info(f"  GridGraphSnapshot: {len(snap.nodes)} nodes, {len(snap.edges)} edges")
    logger.info(f"  Topology hash: {snap.topology_hash}")
    logger.info(f"  Tick count: {snap.tick_count}")

    logger.info(f"\n{'=' * 60}")
    logger.info("BESCOM simulation complete ✓")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

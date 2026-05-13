# dt-sim-pandapower

Fast “per-tick” simulator adapter using **pandapower**.

Responsibilities:
- project a `GridGraphSnapshot` into a `pandapowerNet`
- run `pandapower.runpp` (AC PF) in near-real-time loops
- map results back into the canonical graph state (voltages, flows, load/gen P/Q, etc.)


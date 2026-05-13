# dt-restoration-agent (skeleton)

Autonomous restoration agent (advisory/shadow mode).

This is a **skeleton** implementation that defines:
- an `ActionPlan` generator interface
- a conservative heuristic baseline that emits **no-op** plans unless explicit controllable switches exist in the snapshot
- placeholders for hard safety constraints (radiality, thermal, voltage, lockouts)

Next iterations will:
- enumerate controllable switch edges from GridGraph
- generate sectionalizing + tie-switch restoration candidates
- score candidates via fast PF, then validate finalists with high-fidelity sims


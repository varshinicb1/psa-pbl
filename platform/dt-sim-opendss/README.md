# dt-sim-opendss (skeleton)

OpenDSS adapter for **distribution, unbalanced, DER-heavy** simulation.

PoC integration approach:
- preferred Python bridge: `OpenDSSDirect.py` (package: `opendssdirect`)
- map OpenDSS circuit objects into the canonical `GridGraphSnapshot`
- run solves on demand for calibration/verification (not every tick initially)

This module is a **skeleton**: it provides a safe import boundary, configuration placeholders, and mapping TODOs.


# dt-sim-matpower (skeleton)

MATPOWER integration adapter for transmission PF/OPF benchmarking.

This repo is implemented as a **backend-optional** runner:
- preferred: local **GNU Octave** on PATH (`octave -qf ...`)
- fallback: **Docker** MATPOWER image (requires Docker daemon running)

If neither backend is available, the adapter raises a clear error and unit tests skip.

In the platform plan, this adapter is used for:
- cross-validating pandapower PF results (IEEE cases)
- enabling OPF-based decision support later


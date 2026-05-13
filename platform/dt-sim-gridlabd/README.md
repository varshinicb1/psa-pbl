# dt-sim-gridlabd (skeleton)

GridLAB-D adapter for time-domain / behavioral distribution simulation.

This is a **skeleton** package that:
- provides a runner interface for executing `gridlabd` on a `.glm` model
- captures stdout/stderr and returns a structured result
- is designed to later support HELICS federate mode

Upstream build supports HELICS via CMake flag `GLD_USE_HELICS=ON` (see upstream GridLAB-D README).


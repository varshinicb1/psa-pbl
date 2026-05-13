# GridLAB-D — Architecture & Integration Notes (Initial)

Upstream: `../../../../upstreams/gridlab-d/`

## What it is
GridLAB-D is a C/C++-based distribution simulator focused on **time-domain / behavioral simulation** with realistic device and end-use models.

## Build and federation hook (from upstream README)
The upstream build system uses CMake. Notably, it exposes a build flag:
- `GLD_USE_HELICS=ON/OFF` and `GLD_HELICS_DIR` hints for HELICS integration (see upstream README).

This directly supports the platform plan to use **HELICS** for co-simulation federation.

## Simulation pipeline (high-level)
1. load a GLM model (objects + properties)
2. advance simulation time (event-driven or time-stepped depending on model)
3. emit outputs (tapes/logs) and/or publish values via HELICS when enabled

## Primary integration surface (PoC direction)
PoC integration will start with one of:
1. file-based runner: execute `gridlabd` with a known GLM, parse outputs
2. HELICS federate mode: subscribe/publish boundary quantities and telemetry

## Topology representation (high-level)
GridLAB-D models are object-property based; connectivity emerges from object links. Mapping to `GridGraph` requires:
- stable object IDs for buses/nodes/lines/switches
- explicit mapping for controllable devices (switches, regulators, relays)

## Scalability / performance questions (to answer during deep inspection)
- time-step semantics and cost vs feeder size
- best practices for scenario parameterization (fault injection, switching actions)
- output/streaming strategy for high-rate telemetry


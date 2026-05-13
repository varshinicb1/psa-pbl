# pandapower — Architecture & Integration Notes (Initial)

Upstream: `../../../../upstreams/pandapower/`

## What it is (from upstream README)
pandapower is a Python-based network calculation program for **analysis and optimization of power systems**, built on `pandas`. It is compatible with **MATPOWER / PYPOWER case formats** and supports multiple solvers, including its Newton–Raphson implementation, PYPOWER solvers, and optional C++-backed solvers (e.g., PowerGridModel, lightsim2grid) [see upstream README].

## Core internal data structure
- `pandapowerNet` (`pp.net`) is a dict-like container of pandas DataFrames:
  - `bus`, `line`, `trafo`, `switch`, `load`, `gen`, `sgen`, etc.
  - results in `res_bus`, `res_line`, `res_trafo`, ...

This maps naturally to a unified graph:
- nodes: bus (and optionally bus-phase terminals)
- edges: line/trafo and controllable switch edges

## Simulation pipeline (high-level)
1. build or load `pp.net` (from scratch, or from a case format)
2. run solver (`pp.runpp` for AC PF, `pp.rundcpp` for DC PF, etc.)
3. read `res_*` tables

For near-real-time PoC, pandapower is the default **fast engine** per tick.

## Primary integration surface (PoC direction)
The platform will build/maintain a `pp.net` as a projection of the canonical GridGraph:
- `GridGraphSnapshot` → `pp.net`
- apply actions (switches/setpoints) to `pp.net`
- run `runpp`
- extract results and write updates back into `GridGraphStore`

## Interoperability hooks to confirm during deep inspection
- switch modeling: `net.switch` types and how they affect topology/solves
- transformer tap positions and controls
- measurement models and state-estimation support (if used)
- performance options: solver selection and acceleration

## Scalability / performance questions (to answer during deep inspection)
- best solver choice for repeated solves (NR vs DC vs linear approximations)
- feasibility of incremental updates without reconstructing net
- integration with C++ solvers for speed (optional, later)


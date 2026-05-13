# MATPOWER — Architecture & Integration Notes (Initial)

Upstream: `../../../../upstreams/matpower/`

## What it is (from upstream README)
MATPOWER is a package of **M-files** for MATLAB/Octave to solve **power flow**, continuation power flow, and **optimal power flow** problems. It is widely used for research/education and is designed for performance while staying understandable [see upstream README].

## Core data structures
- “case” structs (`mpc`) containing:
  - `bus`, `gen`, `branch`, plus baseMVA and optional gencost, etc.
- solver entrypoints:
  - `runpf` (power flow)
  - `runopf` (optimal power flow)

## Simulation pipeline (high-level)
1. load case (`case14`, `case118`, … or custom `mpc`)
2. run PF/OPF
3. parse results (`results.bus`, `results.branch`, `results.gen`, …)

## Primary integration surface (PoC direction)
For an open, reproducible PoC, integrate through **GNU Octave**:
- Python writes a strict JSON payload describing the case and requested solve
- Octave script loads JSON → constructs `mpc` → calls `runpf/runopf` → writes JSON results

This provides:
- transmission-level validation/benchmarking
- optional OPF support for restoration ranking and feasibility checks

## Interoperability hooks to confirm during deep inspection
- minimal stable JSON I/O schema for case exchange
- mapping between MATPOWER bus numbering and GridGraph IDs
- how to represent switchable branches (contingencies, outages) in `mpc.branch`

## Scalability / performance questions (to answer during deep inspection)
- repeated PF solve performance (for near-real-time tick loop)
- trade-offs between AC PF and DC approximations for speed


# OpenDSS — Architecture & Integration Notes (Initial)

Upstream: `../../../../upstreams/OpenDSS/`

## What it is (from upstream README)
OpenDSS is a comprehensive electrical power system simulation tool primarily for **electric utility distribution systems**, supporting frequency-domain (sinusoidal steady-state) analyses and many “smart grid / renewables” use cases. It is designed to be **indefinitely expandable**. The `tshort/OpenDSS` repository is marked as an **unofficial mirror** intended for experiments (not upstream development) [see upstream README].

## Simulation pipeline (high-level)
Typical OpenDSS workflows are command-driven:
1. compile/load circuit model (`.dss` scripts)
2. configure solution mode (snapshot / daily / yearly / duty / harmonic, etc.)
3. solve
4. read results (bus voltages, element powers, currents, losses), optionally via monitors/meters

## Topology representation (high-level)
OpenDSS represents a circuit as named objects:
- buses (with per-phase terminals)
- elements: lines, transformers, loads, generators, capacitors, switches, controls

For a unified digital twin, the key is preserving **per-phase terminal modeling** when mapping into `GridGraph`.

## Primary integration surface (PoC direction)
For the PoC platform we will use a Python-facing adapter (planned):
- `OpenDSSDirect.py` or a COM-based interface (Windows) to:
  - enumerate objects + properties
  - execute solve steps
  - extract results and map to/from the canonical `GridGraphSnapshot`

## Interoperability hooks to confirm during deep inspection
- object enumeration APIs (lines/loads/transformers/switches/controls)
- extraction:
  - bus voltages by phase
  - element powers/currents
  - switch/open status and impact on connectivity
- monitors/meters for time-series-like streaming

## Scalability / performance questions (to answer during deep inspection)
- solver performance on large feeders (8,500+ nodes): convergence, step time
- best practice for incremental updates (switch toggles, load changes) vs full recompile
- thread-safety / multi-instance strategy (process-per-feeder vs shared engine)

## Next deep-inspection checklist
- Identify main engine components and data structures for buses/elements
- Locate parser/command interpreter entrypoints
- Identify data export hooks (CSV/JSON?) and stable object identifiers


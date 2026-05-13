# dt-orchestrator

Minimal near-real-time orchestration loop for the PoC:

**ingest → update GridGraphStore → run fast PF (pandapower) → publish**

It provides:
- a replayable tick loop (PoC version)
- a FastAPI service exposing the latest `GridGraphSnapshot`


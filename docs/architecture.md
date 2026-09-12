# Architecture
## Stages and actual files
1. Telemetry — `backend/app/collector.py`, `backend/devices.yaml`.
2. Network state — SQLite `backend/netops.db`: `devices`, `telemetry_history`, `incidents`.
3. Detection — `backend/app/detection.py`: EWMA plus z-score plus sustained window.
4. Root cause — `backend/app/rca.py`: central-overload rule, downstream symptoms.
5. Security — `rca.classify_security`: scan signature and request-rate check.
6. Action planner — `backend/app/planner.py`: `plan` plus `risk_score`.
7. Simulation — `planner.simulate` with capacity guard.
8. Decision — `planner.decide`: `auto`, `approval`, or `rejected`, persisted.
9. Response and UI — `backend/app/api.py` plus `frontend/src/main.js`: simulate, decide, change queue.

## Data flow

```mermaid
flowchart LR
  CFG[devices.yaml] --> COL[Collector]
  COL --> DB[(SQLite network state)]
  INJ[POST /api/inject-fault] --> DB
  DB --> DET[Detection]
  DET --> RCA[Root cause and security]
  RCA --> PLAN[Planner and risk]
  PLAN --> SIM[Simulator and capacity guard]
  SIM --> DEC{auto, approval, rejected}
  DEC --> UI[Control room UI]
  DEC --> AUD[audit events and decisions]
```

## Request flow

```text
Vite UI on port 5173 calls the Python API on port 8000, which reads SQLite netops.db.
```

## Design decisions
- Standard library backend for portability and easy marking.
- Explicit thresholds instead of opaque models.
- Simulation is mandatory before any approval.
- Every automated conclusion is stored with its reason.

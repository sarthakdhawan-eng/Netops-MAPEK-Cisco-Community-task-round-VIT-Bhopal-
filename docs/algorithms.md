# Algorithms

All logic is standard library only, so behaviour is auditable without model dependencies.

## 1. Detection (`backend/app/detection.py`)
- Baseline: EWMA with `alpha = 0.35`.
- Score: z-score of the latest sample against the baseline mean and standard deviation.
- Threshold: `z >= 3.0`.
- Sustained window: at least 3 of the last 3 samples must exceed `z >= 2.0`.
- Outcome: sustained deviation raises an anomaly; a lone spike is held as a false positive with reason `Transient spike`.

## 2. Root cause (`backend/app/rca.py`)
- Input: anomalous devices with detector scores.
- Rule: if a central device (`R-core`) alarms together with downstream devices, the centre is the root and edges are symptoms (confidence 94).
- Fallback: otherwise the highest-score device is the root (confidence 88).

## 3. Security classification (`rca.classify_security`)
- Security when request rate `>= 5000` or at least two scan terms match (`scan`, `port access`, `source ranges`, `req/s`, `brute`).
- Otherwise operational (congestion or failure signature).

## 4. Action planner (`backend/app/planner.py`)
- Security: `Block source IPs`, `Rate limit`, `Isolate device`.
- Critical operational: `Failover`, `Reroute traffic`, `Rate limit`.
- Other operational: `Reroute traffic`, `Rate limit`, `Failover`.

## 5. Risk scoring (`risk_score`)
`blast-radius + severity weight + irreversibility penalty + security uplift`, capped at 95. Factors are returned with every score for transparency.

## 6. Simulation (`simulate`)
Predicted CPU = current CPU + action effect. Fails when prediction exceeds safe capacity or when failover capacity margin is below 20%. Unsafe failover is therefore blocked before any decision.

## 7. Decision policy (`decide`)
- Failed simulation → `rejected`.
- `risk < 20` → `auto`.
- `risk 20–50` → `approval` (security with `risk >= 60` also requires approval).
- Otherwise → `rejected`.

Every outcome is persisted in `decisions` and logged in `audit_events`.

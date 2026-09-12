# Network Model

## Topology

```text
        E-14 (edge gateway)
       /
R-core (core router, central)
       \
        E-19 (edge gateway)

FW-02 (security firewall) → observes ingress toward R-core
```

Declared in `backend/app/rca.py` as `TOPOLOGY`; central set is `{"R-core"}`.

## Devices

| Device | Role | Default host | Method |
|---|---|---|---|
| R-core | Core router | 192.168.1.1 | ping |
| E-14 | Edge gateway | 192.168.1.14 | https |
| E-19 | Edge gateway | 192.168.1.19 | ping |
| FW-02 | Security firewall | 192.168.1.2 | https |

Configure real hosts in `backend/devices.yaml` (see `collector-setup.md`).

## State representation (SQLite `netops.db`)

| Table | Purpose |
|---|---|
| `devices` | Latest reading per device: cpu, latency, loss, state, tone |
| `telemetry` | Seeded range series for charts (`24h`, `7d`, `30d`) |
| `telemetry_history` | Append-only samples written by collector and fault injection |
| `incidents` | Detected or seeded incidents with severity, metric, action, risk |
| `decisions` | Simulation and policy outcomes per action |
| `audit_events` | Detector, collector, simulator, and operator trail |
| `analyst_notes` | Generated assessments per incident |
| `users`, `sessions` | Authentication and 8-hour sessions |

## Key assumption
A central-plus-edge alarm pattern implies central overload rather than independent edge failures. Single-device alarms use the strongest detector score.

# Collector Setup — Extracting Data from Controlled Devices

## What it does
`backend/app/collector.py` polls each controlled device, stores the latest reading in `devices`, appends history to `telemetry_history`, writes `audit_events`, and creates an incident when the statistical detector fires.

Checks used:
- `ping` round-trip latency (Windows and Linux flags handled).
- Optional HTTPS JSON metrics endpoint returning `{"cpu": 42, "loss": 0.4, "latency_ms": 35}`.

## 1. Configure devices
```powershell
cd backend
copy devices.yaml.example devices.yaml
notepad devices.yaml
```

Example:
```yaml
polling_interval_seconds: 30
devices:
  - name: R-core
    role: Core router
    host: 192.168.1.1
    method: ping
  - name: E-14
    role: Edge gateway
    host: 192.168.1.14
    method: https
    metrics_url: https://192.168.1.14/metrics
```

The parser is dependency-free YAML-subset: `- name:` starts a device, `key: value` lines set fields.

## 2. Single poll
```powershell
python -m app.collector --once
```

Expected output:
```text
Collector database: .../netops.db
R-core (192.168.1.1): CPU 40.0% latency 12.0 ms -> Healthy
```

## 3. Continuous polling
```powershell
python -m app.collector --loop --interval 30
```

## 4. Verify extraction
- `GET /api/devices` shows fresh `updated_at` values.
- `GET /api/state` shows collector audit events.
- Sustained overload creates a new `INC-<device>-*`.

## 5. Troubleshooting
- No ping installed or host unreachable: latency falls back to metrics or `35.0 ms`.
- Invalid HTTPS certificate or timeout: metrics default to `cpu 40.0`, `loss 0.4`.
- Missing config: built-in default devices are used.
- Database locked: stop overlapping collectors; SQLite allows one writer.

# API Reference

Base URL: `http://127.0.0.1:8000`. Authenticated routes require `Authorization: Bearer <token>`.

## Public

### POST /api/signup
```json
{"email":"alex@northstar.io","display_name":"Alex","password":"0123456789"}
```
Password minimum is 10 characters. Returns `201 {"created": true}`.

### POST /api/login
```json
{"email":"alex@northstar.io","password":"0123456789"}
```
Returns `{"token":"...","user":{"name":"Alex","email":"..."}}`.

## Authenticated state

### GET /api/state
Returns `{connected, incidents, events, devices}`. Used by the UI on login.

### GET /api/devices
Returns `{devices, connected}`.

### GET /api/telemetry?range=24h|7d|30d
Alias: `GET /api/analytics`. Returns `{range, label, cpu, loss, throughput}`.

### GET /api/profile
Returns the operator profile and workspace.

## Intelligence lifecycle

### POST /api/analyst
```json
{"incident_id":"INC-2048"}
```
Returns `{incident_id, answer, confidence, recommended_action, category, candidates}` with risk-scored actions.

### POST /api/simulate
```json
{"incident_id":"INC-2048","action":"Reroute traffic","capacity_margin":25.0}
```
Returns `{action, risk, factors, reversible, predicted_cpu, passed, reason, decision, execution_mode, device_operation_performed}` and persists the decision. `execution_mode` is `simulation_only`; this route never contacts a device.

### POST /api/decide
```json
{"incident_id":"INC-2048","action":"Reroute traffic","risk":28,"simulated_passed":true,"category":"Operational"}
```
Returns `{decision, scope, execution_mode, device_operation_performed}` where decision is `auto`, `approval`, or `rejected`. This records an API decision only; it does not call the separate in-memory MAPE-K executor or change a device. Both API routes use the same action policy. Unknown actions and invalid simulation capacity are rejected.

The MAPE-K pipeline's executor also only changes in-memory demo state. Its response labels this as `simulation_only`. No network-device adapter is implemented, and no API route performs real device execution. Irreversible actions cannot be auto-approved; rollback is available only for actions marked reversible. Failover rollback restores both the primary and standby snapshots.

## Security defaults

The API binds to `127.0.0.1` by default. Browser origins are denied by default; set `FRONTEND_ORIGIN` to an explicit comma-separated allowlist when serving the UI from a separate origin. Requests are limited to 1 MiB and JSON request bodies must be objects. Health responses do not expose local database paths. These controls do not replace TLS, a production server, rate limiting, or managed secrets when deploying behind a public endpoint.

### POST /api/inject-fault
Injects a telemetry series, runs detection, stores history, and creates an incident when sustained.

Default body is `{}` which injects the R-core overload series. Custom example:
```json
{"device":"E-14","cpu":[40,42,44,43,45,95,96,97],"loss":[0.4,0.5,0.6,0.5,0.7,6.8,7.1,6.9],"throughput":[50,55,60,58,62,88,90,89]}
```

PowerShell example:
```powershell
$headers = @{ Authorization = "Bearer $token" }
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/inject-fault -Method POST -Headers $headers -ContentType "application/json" -Body '{}'
```

### POST /api/events and POST /api/logout
Operational audit writes and session revocation.

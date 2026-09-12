# Demonstration script (8-10 minutes)
## Full lifecycle with expected outputs
1. Normal state: show Overview with healthy devices.
2. Inject fault with an empty body. Detector creates an incident such as `INC-R-core-48211`.
3. Understand with `/api/analyst`. Returns root cause plus security category.
4. Plan: analyst returns candidate actions with risk scores.
5. Evaluate with `/api/simulate` for `Reroute traffic`. Expect pass and predicted CPU near 67.
6. Decide with `/api/decide`. Unsafe `Failover` with low margin returns `rejected`.
7. Respond: approve in UI. Change queue updates and audit events are recorded.

# Test Cases

Implemented in `backend/tests/test_lifecycle.py`. All 8 pass.

| Required scenario | Test | Expected result |
|---|---|---|
| Normal network | `test_normal_network_no_anomaly` | Stable CPU and loss produce no anomaly |
| Single-device failure | `test_single_device_failure_detected` | Sustained CPU and loss deviation is detected |
| Cascading congestion | `test_cascading_congestion_root_cause` | `R-core` is root, edge symptoms explained |
| Security anomaly | `test_security_classification` | Scan pattern is Security, congestion is Operational |
| False positive | `test_false_positive_transient_spike` | Lone spike is held, reason says Transient |
| Unsafe remediation | `test_unsafe_remediation_blocked` | Failover with thin margin fails simulation and is rejected |
| Safe approval path | `test_safe_action_approval_path` | Reroute passes simulation and returns auto or approval |
| API persistence | `test_api_simulate_persists_decision` | Decision row is stored in `decisions` |

Run with `python backend/tests/test_lifecycle.py` from the repository root.

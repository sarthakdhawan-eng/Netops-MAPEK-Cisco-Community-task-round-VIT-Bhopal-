# Presentation Outline (8–10 minutes)

1. Problem and motivation (1 min): raw metrics are not decisions; unsafe automation creates failures.
2. Architecture (1.5 min): show `docs/architecture.md` diagram and request flow.
3. Network model (1 min): central `R-core`, edge symptoms, security sensor.
4. Detection and reasoning (1.5 min): EWMA, z-score, sustained window, false-positive handling.
5. Decision and safety (1.5 min): risk scoring, capacity guard, auto versus approval versus rejected.
6. Live demonstration (2 min): follow `docs/demo.md` through inject, analyst, simulate, unsafe failover block, decide.
7. Limitations and future work (1 min): SNMP drivers, per-device baselines, richer topology, role-based approvals.

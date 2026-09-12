# Evaluation Mapping

| Category and weight | Evidence |
|---|---|
| System Design 25% | Explicit pipeline in `docs/architecture.md`; separate detection, RCA, planner, simulation, decision modules |
| Problem Solving 20% | Central-overload rule distinguishes root from downstream symptoms; transient spikes held as false positives |
| Networking 15% | Topology model, ping and HTTPS extraction, latency and loss handling |
| Security 15% | Operational versus Security classifier; hashed auth; mandatory simulation before risky containment |
| AI and ML 15% | Statistical reasoning documented in `docs/algorithms.md`: EWMA baseline, z-score, sustained window |
| Implementation 5% | Validated: 8 tests pass, frontend build passes, decisions persisted |
| Documentation 2.5% | This folder plus root README and backend README |
| Presentation 2.5% | `docs/presentation-outline.md` and `docs/demo.md` |

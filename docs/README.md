# NetOps Documentation

Start here. This folder documents the prototype intelligent network operations system: Detect → Understand → Plan → Evaluate → Safely Respond.

## Product Snapshot

![NetOps Control Room overview](screenshots/overview.svg)

The image above is a repository-renderable capture of the finished control-room direction. The live UI is available through the frontend quick start in the root [README](../README.md).

## Contents

1. [Problem Statement](problem-statement.md) — challenge, objectives, scope.
2. [Architecture](architecture.md) — stages, data flow, diagram, files.
3. [Network Model](network-model.md) — topology, devices, state representation.
4. [Algorithms](algorithms.md) — detection, root cause, security, risk, simulation, decision.
5. [API Reference](api.md) — endpoints, auth, fault injection walkthrough.
6. [Collector Setup](collector-setup.md) — extracting data from controlled devices.
7. [Demonstration](demo.md) — full lifecycle script with expected outputs.
8. [Test Cases](test-cases.md) — required scenarios and results.
9. [Evaluation Mapping](evaluation-mapping.md) — how the work meets the marking criteria.
10. [Presentation Outline](presentation-outline.md) — 8–10 minute talk plan.

## Quick start

```powershell
cd backend
python -m app.api
python -m app.collector --once
cd ../frontend
npm install
npm run dev
```

Then follow [Demonstration](demo.md) for the complete lifecycle.

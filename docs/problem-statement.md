# Problem Statement

## Context
Modern networks are complex and dynamic. Detecting an incident is only the first step. A network operations system should answer:

- What happened?
- Why did it happen?
- What should be done?
- Is the proposed action safe?

A simple monitor reports raw values (for example, CPU at 94%, packet loss at 12%). A more intelligent system reasons about causes and remedies, while recognising that an automated action can itself create new failures.

## Challenge
Build a system that can:

```text
Detect → Understand → Plan → Evaluate → Safely Respond
```

## Objectives
The prototype must:

1. Maintain a representation of network state.
2. Detect anomalies.
3. Identify probable root causes.
4. Distinguish operational failures from potential security events.
5. Generate possible remediation actions.
6. Evaluate the risk of proposed actions.
7. Simulate the effect of an action before execution.
8. Decide whether an action is executed automatically, submitted for human approval, or rejected.

## Scope of this implementation
Central-overload topology: one core router (`R-core`), two edge gateways (`E-14`, `E-19`), one security firewall (`FW-02`). Central overload cascades into edge symptoms. The security sensor reports scan behaviour separately from congestion.

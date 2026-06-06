# Research Direction

## Research Problem

This benchmark concerns scheduling collective communication over reconfigurable optical networks. The research question is how to reduce communication completion time when collective algorithms require time-varying communication topologies and optical reconfiguration has non-negligible latency.

## Core Contribution

The paper's contribution is schedule-level coordination of data movement and optical topology changes inside a collective operation. Future improvements should work on better scheduling, optimization, or collective/network co-design within this same problem.

## Approach Scope

In-scope work includes alternative exact or heuristic schedulers, improved MILP formulations, decomposition methods, better initialization, additional valid bypass choices, or collective step designs that explicitly target reconfigurable optical networks. Methods may change the scheduler internals as long as they produce valid schedules under the fixed experiment resources.

## Out of Bounds

- Replacing the optical scheduling problem with a different networking model.
- Improving scores by adding optical degree, bandwidth, or faster switching hardware for the same experiment.
- Ignoring collective step barriers or circuit readiness constraints.
- Evaluating by regenerating method outputs inside `eval/` instead of scoring submitted artifacts.

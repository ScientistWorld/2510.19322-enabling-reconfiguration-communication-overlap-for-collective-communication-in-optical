# Research Direction

## Research Problem

This benchmark concerns scheduling collective communication over reconfigurable optical networks. The question is how to minimize communication completion time when collective algorithms need time-varying communication topologies, optical reconfiguration has non-negligible latency, and the schedule must be computed within a fixed per-instance budget.

## Core Contribution

The source paper contributes schedule-level coordination of data movement and optical topology changes inside one collective operation. Future work should improve the schedules produced for this same problem: better completion times on unseen workloads, under the same physical model, resources and compute budget.

## Approach Scope

In scope:
- exact or heuristic schedulers, including improved mathematical-programming formulations;
- decomposition or neighbourhood search, and better initial solutions;
- learned or rule-based guidance that runs inside the solver budget;
- step-structure-aware strategies that apply across collective algorithms, cluster sizes, optical degrees and switching latencies.

Where the reference is weakest:
- many-step collectives (large clusters);
- high optical degree (k=8);
- large messages, where a time-limited solver's incumbent stays close to the lockstep baseline.

## Out of Bounds

- Changing the network model, the collective's steps or the instance parameters.
- Adding optical planes or bandwidth, or shortening switching.
- Ignoring step barriers, circuit readiness or serial plane use.
- Exceeding the per-instance time limit, or using answers computed outside the solver call for the evaluated instance.
- Reporting numbers instead of schedules: the evaluator recomputes everything.

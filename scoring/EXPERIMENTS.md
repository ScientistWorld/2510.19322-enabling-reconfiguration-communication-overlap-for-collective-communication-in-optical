# Experiment Overview

All scored experiments are families of collective-communication workloads. A method is run as a solver on each instance under a fixed per-instance time budget. The evaluator then measures the completion time of the full collective from its own copy of the instance and compares it with the lockstep reconfiguration baseline on that same instance. Each experiment has 6 public train instances and 6 held-out test instances, drawn from the same ranges. One invalid, missing or late schedule anywhere fails the whole run.

## allreduce_scaling (weight 0.40)

Tests whether a scheduler keeps reducing completion time as the cluster grows. The workload is AllReduce on 64 to 1024 nodes over four optical planes, the paper's scalability setting. Larger clusters need longer sequences of distinct topologies, so switching delays accumulate unless the schedule hides them. A scheduler that only does well on small instances loses here.

## collective_algorithms (weight 0.40)

Tests whether the gains carry across different collective algorithms and message sizes at a high optical degree (eight planes). The algorithms are reduce-scatter, AllReduce and two all-to-all variants, with payloads from 1 MB to 512 MB. This covers both the latency-dominated regime (switching costs more than transmission) and the bandwidth-dominated one. With eight planes the space of possible schedules is large, so this is where a time-limited scheduler has the most room to improve.

## hardware_sensitivity (weight 0.20)

Tests robustness to the optical hardware: two, four or eight planes, and switching latencies from 0.02 ms to 20 ms. A good scheduler should stay valid and keep its advantage over the lockstep baseline from fast to slow switches and from narrow to wide optical degree.

## Unscored reproduction checks (`scores.json` only)

`_paper_fig5_rabenseifner_allreduce_8node`, `_paper_fig8_rabenseifner_allreduce_64node_k4` and `_paper_fig8_rabenseifner_allreduce_512node_k4` report completion time and reduction on the paper's own named instances. They are public and small, so they are reproduction checks, not ranked targets.

# Experiment Overview

All scored experiments are families of collective-communication workloads. A method is run as a solver on each instance under a fixed per-instance compute budget (CPU time, counted by the evaluator). The evaluator then measures the completion time of the full collective from its own copy of the instance and compares it with the lockstep reconfiguration baseline on that same instance. Public train instances and held-out test instances are drawn from the same settings with the same mix of difficulty. One invalid, missing or over-budget schedule anywhere fails the whole run.

Within each family, payloads are chosen so that the share of the lockstep schedule's time spent switching topology is spread evenly over a band (from 35% up to 80-92%). Below that band, almost any schedule is as good as lockstep; above it, the problem has a near-trivial answer. Inside it, how well a scheduler hides switching delays decides the result.

## allreduce_scaling (weight 0.40)

Tests whether a scheduler keeps reducing completion time as the cluster grows. The workload is AllReduce on 64 to 1024 nodes over four optical planes, the paper's scalability setting (10 instances per slice). Larger clusters need longer sequences of distinct topologies, so switching delays accumulate unless the schedule hides them. A scheduler that only does well on short collectives loses here.

## high_optical_degree (weight 0.30)

Tests whether the gains hold when there are many parallel optical planes (eight), for reduce-scatter on 128 to 1024 nodes with payloads from 1 MB to 512 MB (12 instances per slice). With eight planes the space of possible schedules is very large, and the paper itself notes that its time-limited solver can return sub-optimal schedules in this regime.

## hardware_sensitivity (weight 0.30)

Tests robustness to the optical hardware: two, four or eight planes, and switching latencies from 0.02 ms to 20 ms, each combination once, across reduce-scatter, AllReduce and two all-to-all algorithms (12 instances per slice; all four algorithms with two planes, reduce-scatter and AllReduce with four, reduce-scatter with eight; see below). Payloads sit around the point where transmission time and switching time are comparable, which is where a scheduler's choices matter most. A good scheduler should stay valid and keep its advantage from fast to slow switches and from narrow to wide optical degree.

## Not scored: long or all-distinct collectives on many planes

AllReduce, Bruck and Pairwise All-to-All with eight planes, Bruck and Pairwise All-to-All with four planes, and collectives on more than 1024 nodes are not part of the scored families. There a simple fixed schedule pattern already does as well as the reference scheduler or better (on AllReduce with eight planes, and on AllReduce and reduce-scatter beyond 1024 nodes, the reference's schedules are mostly no better than the lockstep baseline), so the setting would reward a hand-written pattern rather than scheduling.

## Unscored reproduction checks (`scores.json` only)

`_paper_fig5_rabenseifner_allreduce_8node`, `_paper_fig8_rabenseifner_allreduce_64node_k4` and `_paper_fig8_rabenseifner_allreduce_512node_k4` report completion time and reduction on the paper's own named instances. They are public and small, so they are reproduction checks, not ranked targets.

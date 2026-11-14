# Evaluation

## Interface: methods are solvers

A method is a script `scripts/solvers/<method>.sh`. Every evaluator calls it from the workspace root, once per workload instance:

```
bash scripts/solvers/<method>.sh INSTANCE_JSON OUTPUT_JSON CPU_BUDGET_S
```

- `INSTANCE_JSON` holds `optical_degree` (k), `per_link_gbps`, `base_latency_us`, `reconfig_latency_us`, `nodes`, `algorithm`, `payload_mb` and the ordered `steps` (`step`, `config`, `message_mb`).
- `CPU_BUDGET_S` is 120: the source paper's per-instance solver budget, counted as **CPU time** by the evaluator over the solver's whole process tree (every process the solver starts, including detached ones, is reaped and counted). Using more than 120 CPU-seconds on any instance is a failure. Each process is also hard-limited to about 125 CPU-seconds, and a wall-clock cap of 300 s stops hung or sleeping solvers. Make your solver's work budget deterministic if you want repeatable scores (e.g. iteration or node counts rather than time).
- The solver writes `{"schedule": [...]}` to `OUTPUT_JSON`. One entry per (step, plane) that carries data, with numeric fields `step`, `plane`, `message_mb`, `transmit_start_us`, `transmit_end_us`, and, when that plane must switch topology before this transmission, `reconfig_start_us` and `reconfig_end_us`. Optional `reconfigured` (0/1) and `config` must agree with the instance if present. Anything else in the file is ignored.

The scored method key is **`swot`**; it is always reported (a missing `scripts/solvers/swot.sh` is a failed run). Every other `scripts/solvers/*.sh` on disk is scored too. `scripts/solvers/swot.sh` currently runs the reproduced paper method; replace it with your own solver.

## What is computed

For every instance the evaluator re-derives everything from the schedule and its own frozen copy of the instance (`problem.md` lists the rules): plane indices, per-step volume conservation, transmission time `>= d/B + T_lat`, switching duration `>= T_recfg` whenever a plane's topology changes, no switching while transmitting, transmission only after the circuit is ready, and step barriers. CCT is the latest transmission end measured from time 0. Times have a tolerance of `1e-3 us + 1e-6 x` the baseline CCT.

The baseline is computed by the evaluator from the frozen instance: **Strawman-ICR (lockstep)** - every plane serves every step with an even split, and all planes switch together whenever consecutive steps need different topologies.

## Metrics (per experiment)

- `cct_reduction_vs_strawman_pct` (primary, higher is better): mean over the experiment's instances of `100 * (CCT_strawman - CCT) / CCT_strawman`, each instance clipped to [-100, 100].
- `valid_schedule` (constraint, higher is better): 1 when the run produced a valid schedule within the budget for every instance of every experiment.

**Failure rule.** If any instance (in any experiment) is missing, over budget, non-zero exit, unparseable or physically invalid, the whole run fails: every metric of every experiment gets its worst value (`-100` and `0`). Numbers the solver writes itself (CCTs, validity flags, specs, baselines) are never read. The CPU-seconds each instance used are reported under `_status` (not scored).

## Experiments

Three families from the source paper's evaluation (see `scoring/EXPERIMENTS.md`):

- `allreduce_scaling` (weight 0.40, 10 instances per slice): Rabenseifner AllReduce, 64-1024 nodes, k=4.
- `high_optical_degree` (weight 0.30, 12 instances per slice): Rabenseifner ReduceScatter, 128-1024 nodes, k=8.
- `hardware_sensitivity` (weight 0.30, 12 instances per slice): every combination of k in {2,4,8} and switching latency 0.02-20 ms once; four algorithms at k=2, no Bruck at k=4, ReduceScatter at k=8.

In every family the payloads are spread so that the share of the lockstep time spent switching covers the family's band evenly; train and test have the same mix.

## Train and test

- `bash scripts/evaluate_train.sh` -> `scoring/scores_train.json`: public instances in `eval/train/instances.json`. Train schedules are kept in `checkpoints/train/<method>/`.
- `bash scripts/evaluate_test.sh` -> `scoring/scores_test.json`: held-out instances of the same families, ranges and difficulty mix; scored the same way. Takes no arguments.
- `bash scripts/evaluate.sh` -> `scoring/scores_train.json` and `scoring/scores.json` (train experiments plus unscored `_paper_*` checks on the paper's own Fig. 5 and Fig. 8 instances, with `cct_us`).

Each run costs up to 2 CPU-minutes per instance per method (34 train + 3 paper instances for `evaluate.sh`, 34 test instances for the hidden test).

## Paper reference points

Strawman-ICR vs the paper's scheduler: 1500 -> 1200 us (20%) on the 8-node, k=2 example; 39.6% at 64 nodes and 46.9% at 512 nodes for AllReduce with k=4; peaks of 85-89% across algorithms with k=8. They are kept in `scoring/reference.json` under `_` keys and as labelled anchors; they are single points or peaks, not the family means the gym scores.

## Rules

All comparisons use the frozen instance: same steps, optical degree, bandwidth, base latency and switching latency. Do not add planes or bandwidth, shorten switching, skip barriers, or change the collective's steps.

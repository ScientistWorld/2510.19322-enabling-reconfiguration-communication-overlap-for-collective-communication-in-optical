# Evaluation

## Interface: methods are solvers

A method is a script `scripts/solvers/<method>.sh`. Every evaluator calls it from the workspace root, once per workload instance:

```
bash scripts/solvers/<method>.sh INSTANCE_JSON OUTPUT_JSON TIME_LIMIT_S
```

- `INSTANCE_JSON` holds `optical_degree` (k), `per_link_gbps`, `base_latency_us`, `reconfig_latency_us`, `nodes`, `algorithm`, `payload_mb` and the ordered `steps` (`step`, `config`, `message_mb`).
- `TIME_LIMIT_S` is 120 (the source paper's solver limit). The process group is killed 150 s after it starts; a killed or non-zero exit counts as a failure.
- The solver writes `{"schedule": [...]}` to `OUTPUT_JSON`. One entry per (step, plane) that carries data, with numeric fields `step`, `plane`, `message_mb`, `transmit_start_us`, `transmit_end_us`, and, when that plane must switch topology before this transmission, `reconfig_start_us` and `reconfig_end_us`. Optional `reconfigured` (0/1) and `config` must agree with the instance if present. Anything else in the file is ignored.

The scored method key is **`swot`**; it is always reported (a missing `scripts/solvers/swot.sh` is a failed run). Every other `scripts/solvers/*.sh` on disk is scored too. `scripts/solvers/swot.sh` currently runs the reproduced paper method; replace it with your own solver.

## What is computed

For every instance the evaluator re-derives everything from the schedule and its own frozen copy of the instance (`problem.md` lists the rules): plane indices, per-step volume conservation, transmission time `>= d/B + T_lat`, switching duration `>= T_recfg` whenever a plane's topology changes, no switching while transmitting, transmission only after the circuit is ready, and step barriers. CCT is the latest transmission end measured from time 0. Times have a tolerance of `1e-3 us + 1e-6 x` the baseline CCT.

The baseline is computed by the evaluator from the frozen instance: **Strawman-ICR (lockstep)** - every plane serves every step with an even split, and all planes switch together whenever consecutive steps need different topologies.

## Metrics (per experiment)

- `cct_reduction_vs_strawman_pct` (primary, higher is better): mean over the experiment's instances of `100 * (CCT_strawman - CCT) / CCT_strawman`, each instance clipped to [-100, 100].
- `valid_schedule` (constraint, higher is better): 1 when the run produced a valid schedule for every instance of every experiment.

**Failure rule.** If any instance (in any experiment) is missing, late, non-zero exit, unparseable or physically invalid, the whole run fails: every metric of every experiment gets its worst value (`-100` and `0`). Numbers the solver writes itself (CCTs, validity flags, specs, baselines) are never read.

## Experiments

Three families from the source paper's evaluation, 6 instances each per slice (see `scoring/EXPERIMENTS.md`):

- `allreduce_scaling` (weight 0.40): Rabenseifner AllReduce, 64-1024 nodes, k=4.
- `collective_algorithms` (weight 0.40): four collective algorithms, k=8.
- `hardware_sensitivity` (weight 0.20): k in {2,4,8} and switching latency 0.02-20 ms.

Every instance is too large to enumerate plane-usage patterns within the budget.

## Train and test

- `bash scripts/evaluate_train.sh` -> `scoring/scores_train.json`: public instances in `eval/train/instances.json` (includes the paper's Fig. 8 64- and 512-node AllReduce points). Train schedules are kept in `checkpoints/train/<method>/`.
- `bash scripts/evaluate_test.sh` -> `scoring/scores_test.json`: held-out instances of the same families and ranges; scored the same way. Takes no arguments.
- `bash scripts/evaluate.sh` -> `scoring/scores_train.json` and `scoring/scores.json` (train experiments plus unscored `_paper_*` checks on the paper's own Fig. 5 and Fig. 8 instances, with `cct_us`).

Each run costs up to ~2.5 min per instance per method (18 train + 3 paper instances for `evaluate.sh`, 18 test instances for the hidden test).

## Paper reference points

Strawman-ICR vs the paper's scheduler: 1500 -> 1200 us (20%) on the 8-node, k=2 example; 39.6% at 64 nodes and 46.9% at 512 nodes for AllReduce with k=4; peaks of 85-89% across algorithms with k=8. They are kept in `scoring/reference.json` under `_` keys and as labelled anchors; they are single points or peaks, not the family means the gym scores.

## Rules

All comparisons use the frozen instance: same steps, optical degree, bandwidth, base latency and switching latency. Do not add planes or bandwidth, shorten switching, skip barriers, or change the collective's steps.

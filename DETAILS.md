# Overview

- **Paper ID:** 2510.19322
- **Title:** Enabling Reconfiguration-Communication Overlap for Collective Communication in Optical Networks
- **Domain:** Distributed systems / optical networking / collective communication
- **TL;DR:** The paper schedules optical topology reconfiguration inside collective communication operations so switching latency is hidden behind data transmission.

## Short Summary

The paper studies collective communication in distributed ML clusters connected by optical circuit switches. Dynamic collective algorithms need changing topologies, but static optical configurations waste bandwidth and naive per-step reconfiguration pays high switching latency. SWOT addresses this with an offline MILP scheduler that jointly chooses message splits, reconfiguration timing, and topology bypasses. Simulations show lower communication completion time across several collective algorithms and network settings.

## Key Results

- In the paper's 8-node Rabenseifner AllReduce example, CCT drops from 1500 us to 1200 us.
- Across algorithm-level simulations, reported peak CCT reductions reach 89.7%.
- The method remains valid across optical degrees and reconfiguration latencies from 0.02 ms to 20 ms.

---

# Problem Definition

## Research Question

How can a scheduler minimize collective-communication completion time (CCT) in an optical circuit switched cluster when the collective algorithm requires a sequence of changing pairwise communication topologies and switching a topology takes non-negligible time?

## Setting

`p` compute nodes are connected by `k` parallel optical planes (one optical circuit switch per plane). Every node has one interface per plane; the per-node bandwidth is fixed at 800 Gbps, so each plane runs at `B = 800/k` Gbps. A collective operation (AllReduce, ReduceScatter, All-to-All, ...) implemented by a given algorithm is an ordered list of communication steps. Each step has

- a required topology (an integer ID; equal IDs within one collective mean the same pairing), and
- a per-node message volume in MB.

Steps are sequential: step `i+1` relies on data produced by step `i`.

## What a schedule decides

For every step, which planes carry part of that step's volume and how much each carries, when each plane switches topology, and when each transmission starts. The physical rules every schedule must satisfy:

1. **Traffic conservation.** The volumes carried in a step sum to the step's volume; every listed transmission carries a positive volume on a plane index in `[0, k)`.
2. **Transmission time (alpha-beta model).** A plane carrying `d` MB in a step is busy for at least `d / B + T_lat`, with `B` in MB/us (`Gbps / 8000`) and base latency `T_lat`.
3. **Circuit readiness.** A plane carries a step only if it is configured for that step's topology. Changing a plane's topology takes `T_recfg`; the plane cannot transmit while switching and only starts switching after its previous transmission ends. A plane's first use needs no switch (planes are configured before the collective starts); a later use with the same topology as that plane's previous use needs no switch.
4. **Serial use.** A plane does one thing at a time.
5. **Step barrier.** No transmission of step `i+1` starts before every transmission of step `i` has ended.

The collective starts at time 0; its CCT is the end of the last transmission.

## Workloads

Instances come from the collective algorithms and network settings of the source paper's evaluation (see `data/collectives.py` for generators and family settings): Rabenseifner ReduceScatter / AllReduce (recursive halving/doubling), Bruck All-to-All and Pairwise-exchange All-to-All, on 9-1024 nodes (7-20 steps), with `k` in {2, 4, 8}, `T_lat` = 20 us and `T_recfg` from 20 us to 20 ms. Payloads are chosen per instance so that switching is a material but not total share of the lockstep schedule's time (between 35% and 80-92% of it), which is where schedules differ. Public train instances are in `eval/train/instances.json`; held-out test instances are drawn from the same families and ranges.

## Why It Matters

Distributed ML training spends substantial time in collective communication. Optical circuit switches provide high bandwidth, but a fixed topology cannot serve dynamic communication patterns with limited optical degree, and naively switching every plane at every step adds the switching delay to the critical path.

## Success Criteria

Valid schedules with lower CCT than the naive lockstep reconfiguration baseline (all planes serve every step with an even split and switch together whenever the topology changes), under fixed optical resources, bandwidth, latencies and collective workload, produced within a fixed per-instance compute budget (120 CPU-seconds, counted by the evaluator).

---

# Paper's Method

## Key Contribution

The paper proposes SWOT, an offline scheduler for collective communication over optical circuit switched networks. SWOT makes intra-collective topology reconfiguration practical by overlapping reconfiguration with data transmission.

## Approach

SWOT formulates collective execution as a mixed-integer linear program. For every collective step and optical plane, it decides the message volume assigned to that plane, whether the plane reconfigures, and the transmission and reconfiguration timing. The objective is to minimize communication completion time.

The scheduler implements three coupled mechanisms:

- Heterogeneous message splitting: unevenly divide a step's traffic across optical planes.
- Asynchronous overlapping: allow one plane to reconfigure while another plane is still transmitting.
- Topology bypassing: skip intermediate topologies on planes that are not used for those steps.

The constraints enforce traffic conservation, transmission duration under an alpha-beta model, reconfiguration duration, circuit readiness before transmission, serial resource use per OCS plane, and global step barriers required by collective algorithms.

## Reproduction (`method/swot_scheduler.py`, exposed as `scripts/solvers/swot.sh`)

- The paper's MILP (Eqs. 1-11). The `last_cfg`/`s_ij` bypass logic is linearized with pairwise "most recent previous use" implications; the paper's own `last_cfg` encoding is available (`build_model(..., formulation="paper")`), has the same optimum, and was about twice as slow per CBC node with no better incumbents in a probe, so it is not the default. A plane's first use is free (planes are pre-configured), as in the paper's Fig. 5.
- Solved with CBC via PuLP, CBC's default single-threaded search, fixed CBC seeds.
- **Budget.** The paper uses a 120 s CBC time limit. A time limit makes the schedule depend on the machine and on whatever runs beside it, so the reproduction gives CBC no time limit at all and stops it after a fixed number of branch-and-bound nodes instead (`method/budget.json`): 5800 nodes for collectives of up to 14 steps, scaled by (14 / steps)^2 for longer ones (CBC's node rate fell about that fast with the number of steps). The budget was calibrated once on the compute node; on the scored instances CBC then uses 1-100 of the 120 CPU-seconds, and the schedule is the same under any load (two independent runs of the hidden test, and a run with every CPU busy, gave identical schedules). CBC's clock is set to CPU time and it never sees a time limit; the only other stop is a CPU-time kill switch on the CBC process (8 CPU-s below the evaluator's budget) that has never fired on the scored instances; if it did, the lockstep schedule would be written. PuLP is pinned to 3.3.2, whose bundled CBC binary produced the reference numbers.
- The paper leaves the big-M constant unspecified. The reproduction uses the lockstep (Strawman-ICR) completion time as M and bounds the CCT by it. The lockstep schedule is feasible, so the MILP optimum is unchanged (`--big-m horizon` keeps the loose variant of earlier iterations).
- The MILP's plane-use/split decisions are written with exact earliest-start timing. If CBC returns no incumbent, the lockstep schedule is written.

## Main Claims

The primary claim is that demand-aware overlapping schedules reduce CCT compared with naive intra-collective reconfiguration and static optical scheduling while preserving collective correctness. The paper reports a 20% reduction in its 8-node design-intuition example and peak reductions up to 89.7% across larger simulated collective workloads.

---

# Evaluation

## Interface: methods are solvers

A method is a script `scripts/solvers/<method>.sh`. Every evaluator calls it from the workspace root, once per workload instance:

```
bash scripts/solvers/<method>.sh INSTANCE_JSON OUTPUT_JSON CPU_BUDGET_S
```

- `INSTANCE_JSON` holds `optical_degree` (k), `per_link_gbps`, `base_latency_us`, `reconfig_latency_us`, `nodes`, `algorithm`, `payload_mb` and the ordered `steps` (`step`, `config`, `message_mb`).
- `CPU_BUDGET_S` is 120: the source paper's per-instance solver budget, counted as **CPU time** by the evaluator over the solver's whole process tree (every process the solver starts, including detached ones, is reaped and counted). Using more than 120 CPU-seconds on any instance is a failure. Each process is also hard-limited to 135 CPU-seconds (a backstop against runaway processes), and a wall-clock cap of 300 s stops hung or sleeping solvers. Make your solver's work budget deterministic if you want repeatable scores (e.g. iteration or node counts rather than time).
- The solver writes `{"schedule": [...]}` to `OUTPUT_JSON`. One entry per (step, plane) that carries data, with numeric fields `step`, `plane`, `message_mb`, `transmit_start_us`, `transmit_end_us`, and, when that plane must switch topology before this transmission, `reconfig_start_us` and `reconfig_end_us`. Optional `reconfigured` (0/1) and `config` must agree with the instance if present. Anything else in the file is ignored.

The scored method key is **`swot`**; it is always reported (a missing `scripts/solvers/swot.sh` is a failed run). Every other `scripts/solvers/*.sh` on disk is scored too. `scripts/solvers/swot.sh` currently runs the reproduced paper method; replace it with your own solver.

## What is computed

For every instance the evaluator re-derives everything from the schedule and its own frozen copy of the instance (`problem.md` lists the rules): plane indices, per-step volume conservation, transmission time `>= d/B + T_lat`, switching duration `>= T_recfg` whenever a plane's topology changes, no switching while transmitting, transmission only after the circuit is ready, and step barriers. CCT is the latest transmission end measured from time 0. Times have a tolerance of `1e-3 us + 1e-6 x` the baseline CCT.

The baseline is computed by the evaluator from the frozen instance: **Strawman-ICR (lockstep)** - every plane serves every step with an even split, and all planes switch together whenever consecutive steps need different topologies.

## Metrics (per experiment)

- `cct_reduction_vs_strawman_pct` (primary, higher is better): mean over the experiment's instances of `100 * (CCT_strawman - CCT) / CCT_strawman`, each instance clipped to [-100, 100].
- `valid_schedule` (constraint, higher is better): 1 when the run produced a valid schedule within the budget for every instance of every experiment.

**Failure rule.** If any instance (in any experiment) is missing, over budget, non-zero exit, unparseable or physically invalid, the whole run fails: every metric of every experiment gets its worst value (`-100` and `0`). Before any solver runs, the evaluator writes the output file with every method failed; it is replaced only when every method has been scored, so an evaluator that is killed or crashes leaves worst values, not a missing entry. Numbers the solver writes itself (CCTs, validity flags, specs, baselines) are never read. The CPU-seconds each instance used are reported under `_status` (not scored).

## Experiments

Three families from the source paper's evaluation (see `scoring/EXPERIMENTS.md`):

- `allreduce_scaling` (weight 0.40, 10 instances per slice): Rabenseifner AllReduce, 64-1024 nodes, k=4.
- `high_optical_degree` (weight 0.30, 12 instances per slice): Rabenseifner ReduceScatter, 128-1024 nodes, k=8.
- `hardware_sensitivity` (weight 0.30, 12 instances per slice): every combination of k in {2,4,8} and switching latency 0.02-20 ms once; four algorithms at k=2, ReduceScatter and AllReduce at k=4, ReduceScatter at k=8.

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

---

# Reproduction Log

### Iteration 1: gpt-5.5
- **Milestone**: `none` | **Status**: error
- **Working time**: 15m | **GPU**: 0.0h

<details>
<summary>Progress Log</summary>

<!-- Write your progress here -->

</details>

### Iteration 1: gpt-5.5
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 9m | **GPU**: 0.0h
- **Jobs**: 1 total (1 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-06 05:45] - none
- Read the paper and identified the core method as a PuLP/CBC MILP scheduler for reconfiguration-communication overlap.
- Implemented the initial workload definitions, baseline simulator, SWOT scheduler, method-agnostic evaluator, scripts, scoring reference, and benchmark documentation.
- Preparing first CPU job to verify the method runs end-to-end inside the managed container.

### [2026-06-06 06:20] - none
- Audited the implementation and confirmed it targets the paper's MILP scheduling method rather than a surrogate.
- Fixed scoring issues so default scores match the paper-reported reference experiment and evaluation independently validates submitted schedules.
- Resubmitting a CPU smoke job because no completed `checkpoints/` artifacts were present.

### [2026-06-06 06:55] - core_claim
- Completed the managed CPU smoke job successfully.
- Ran the paper's SWOT MILP scheduler and the strawman ICR baseline on the Fig. 5 Rabenseifner AllReduce timing target.
- Reproduced the paper's core timing claim: strawman ICR CCT 1500 us, SWOT CCT 1200 us, and 20.0% CCT reduction.
- Verified `scoring/reference.json` and `scoring/scores.json` with `python validate.py --compare`; all structure, separation, and score checks passed.

</details>

### Iteration 2: gpt-5.5
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 5m | **GPU**: 0.0h
- **Jobs**: 1 total (1 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-06 05:35] - method_runs
- Implemented the SWOT MILP scheduler with heterogeneous message splitting, asynchronous per-plane reconfiguration timelines, and topology bypassing.
- Ran the baseline, method, and evaluator end-to-end in managed job `7126c74f-64d`.

### [2026-06-06 05:40] - core_claim
- Reproduced the paper's Fig. 5 core claim: SWOT reduces CCT from 1500.0 us for Strawman-ICR to 1200.0 us.
- Independent evaluator confirmed the generated SWOT schedule is valid and preserves collective step ordering, per-plane serial resource use, and transmission-after-reconfiguration precedence.

### [2026-06-06 05:50] - core_claim
- Continuation audit re-read `method/`, `data/`, `baseline/`, and `eval/`; the implementation is a real SWOT MILP scheduler, not a surrogate.
- Re-ran standalone `scripts/evaluate.sh` and `python validate.py --compare`; scores still match the paper's Fig. 5 target and all separation checks pass.

</details>

### Iteration 3: gpt-5.5
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 9m | **GPU**: 0.0h
- **Jobs**: 2 total (2 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-06 01:35] - core_claim
- Managed CPU job ran `scripts/reproduce.sh` successfully.
- Reproduced the paper's Fig. 5 Rabenseifner AllReduce example: Strawman-ICR 1500 us, SWOT 1200 us, 20% CCT reduction, valid schedule.

### [2026-06-06 05:48] - core_claim
- Added two paper Fig. 8 AllReduce scalability targets to the benchmark plan.
- Fixed evaluator artifact merging so `eval/` independently validates generated schedules from their workload specs.
- Tightened topology-bypass consistency so repeated use of the same plane/configuration cannot report a redundant reconfiguration.

### [2026-06-06 05:58] - core_claim_plus
- Managed CPU job `f4fb2013-489` regenerated all registered baseline and SWOT artifacts in the container.
- Reproduced Fig. 5 exactly: Strawman-ICR 1500 us, SWOT 1200 us, 20.0% CCT reduction, valid schedule.
- Reproduced the same claim on two Fig. 8 scalability settings with valid schedules: 64-node AllReduce reduction 35.89% versus the paper's 39.6%, and 512-node AllReduce reduction 42.09% versus the paper's 46.9%.
- `python validate.py --compare` passed, including evaluation/method import separation and checks that evaluation reads generated artifacts.

</details>

### Iteration 4: gpt-5.5 (designer_stage_1)
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 5m | **GPU**: 0.0h
- **Jobs**: 2 total (2 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-06 01:35] - core_claim
- Managed CPU job ran `scripts/reproduce.sh` successfully.
- Reproduced the paper's Fig. 5 Rabenseifner AllReduce example: Strawman-ICR 1500 us, SWOT 1200 us, 20% CCT reduction, valid schedule.

### [2026-06-06 05:48] - core_claim
- Added two paper Fig. 8 AllReduce scalability targets to the benchmark plan.
- Fixed evaluator artifact merging so `eval/` independently validates generated schedules from their workload specs.
- Tightened topology-bypass consistency so repeated use of the same plane/configuration cannot report a redundant reconfiguration.

### [2026-06-06 05:58] - core_claim_plus
- Managed CPU job `f4fb2013-489` regenerated all registered baseline and SWOT artifacts in the container.
- Reproduced Fig. 5 exactly: Strawman-ICR 1500 us, SWOT 1200 us, 20.0% CCT reduction, valid schedule.
- Reproduced the same claim on two Fig. 8 scalability settings with valid schedules: 64-node AllReduce reduction 35.89% versus the paper's 39.6%, and 512-node AllReduce reduction 42.09% versus the paper's 46.9%.
- `python validate.py --compare` passed, including evaluation/method import separation and checks that evaluation reads generated artifacts.

</details>

### Iteration 5: gpt-5.5 (designer_stage_2)
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 5m | **GPU**: 0.0h
- **Jobs**: 2 total (2 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-06 01:35] - core_claim
- Managed CPU job ran `scripts/reproduce.sh` successfully.
- Reproduced the paper's Fig. 5 Rabenseifner AllReduce example: Strawman-ICR 1500 us, SWOT 1200 us, 20% CCT reduction, valid schedule.

### [2026-06-06 05:48] - core_claim
- Added two paper Fig. 8 AllReduce scalability targets to the benchmark plan.
- Fixed evaluator artifact merging so `eval/` independently validates generated schedules from their workload specs.
- Tightened topology-bypass consistency so repeated use of the same plane/configuration cannot report a redundant reconfiguration.

### [2026-06-06 05:58] - core_claim_plus
- Managed CPU job `f4fb2013-489` regenerated all registered baseline and SWOT artifacts in the container.
- Reproduced Fig. 5 exactly: Strawman-ICR 1500 us, SWOT 1200 us, 20.0% CCT reduction, valid schedule.
- Reproduced the same claim on two Fig. 8 scalability settings with valid schedules: 64-node AllReduce reduction 35.89% versus the paper's 39.6%, and 512-node AllReduce reduction 42.09% versus the paper's 46.9%.
- `python validate.py --compare` passed, including evaluation/method import separation and checks that evaluation reads generated artifacts.

</details>

### Iteration 6: gpt-5.5 (designer_stage_3)
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 6m | **GPU**: 0.0h
- **Jobs**: 4 total (4 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-06 01:35] - core_claim
- Managed CPU job ran `scripts/reproduce.sh` successfully.
- Reproduced the paper's Fig. 5 Rabenseifner AllReduce example: Strawman-ICR 1500 us, SWOT 1200 us, 20% CCT reduction, valid schedule.

### [2026-06-06 05:48] - core_claim
- Added two paper Fig. 8 AllReduce scalability targets to the benchmark plan.
- Fixed evaluator artifact merging so `eval/` independently validates generated schedules from their workload specs.
- Tightened topology-bypass consistency so repeated use of the same plane/configuration cannot report a redundant reconfiguration.

### [2026-06-06 05:58] - core_claim_plus
- Managed CPU job `f4fb2013-489` regenerated all registered baseline and SWOT artifacts in the container.
- Reproduced Fig. 5 exactly: Strawman-ICR 1500 us, SWOT 1200 us, 20.0% CCT reduction, valid schedule.
- Reproduced the same claim on two Fig. 8 scalability settings with valid schedules: 64-node AllReduce reduction 35.89% versus the paper's 39.6%, and 512-node AllReduce reduction 42.09% versus the paper's 46.9%.
- `python validate.py --compare` passed, including evaluation/method import separation and checks that evaluation reads generated artifacts.

</details>

### Iteration 7: gpt-5.5 (packager)
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 4m | **GPU**: 0.0h
- **Jobs**: 4 total (4 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-06 01:35] - core_claim
- Managed CPU job ran `scripts/reproduce.sh` successfully.
- Reproduced the paper's Fig. 5 Rabenseifner AllReduce example: Strawman-ICR 1500 us, SWOT 1200 us, 20% CCT reduction, valid schedule.

### [2026-06-06 05:48] - core_claim
- Added two paper Fig. 8 AllReduce scalability targets to the benchmark plan.
- Fixed evaluator artifact merging so `eval/` independently validates generated schedules from their workload specs.
- Tightened topology-bypass consistency so repeated use of the same plane/configuration cannot report a redundant reconfiguration.

### [2026-06-06 05:58] - core_claim_plus
- Managed CPU job `f4fb2013-489` regenerated all registered baseline and SWOT artifacts in the container.
- Reproduced Fig. 5 exactly: Strawman-ICR 1500 us, SWOT 1200 us, 20.0% CCT reduction, valid schedule.
- Reproduced the same claim on two Fig. 8 scalability settings with valid schedules: 64-node AllReduce reduction 35.89% versus the paper's 39.6%, and 512-node AllReduce reduction 42.09% versus the paper's 46.9%.
- `python validate.py --compare` passed, including evaluation/method import separation and checks that evaluation reads generated artifacts.

</details>

### Iteration 8: gpt-5.5 (verifier)
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 10m | **GPU**: 0.0h
- **Jobs**: 4 total (4 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-06 01:35] - core_claim
- Managed CPU job ran `scripts/reproduce.sh` successfully.
- Reproduced the paper's Fig. 5 Rabenseifner AllReduce example: Strawman-ICR 1500 us, SWOT 1200 us, 20% CCT reduction, valid schedule.

### [2026-06-06 05:48] - core_claim
- Added two paper Fig. 8 AllReduce scalability targets to the benchmark plan.
- Fixed evaluator artifact merging so `eval/` independently validates generated schedules from their workload specs.
- Tightened topology-bypass consistency so repeated use of the same plane/configuration cannot report a redundant reconfiguration.

### [2026-06-06 05:58] - core_claim_plus
- Managed CPU job `f4fb2013-489` regenerated all registered baseline and SWOT artifacts in the container.
- Reproduced Fig. 5 exactly: Strawman-ICR 1500 us, SWOT 1200 us, 20.0% CCT reduction, valid schedule.
- Reproduced the same claim on two Fig. 8 scalability settings with valid schedules: 64-node AllReduce reduction 35.89% versus the paper's 39.6%, and 512-node AllReduce reduction 42.09% versus the paper's 46.9%.
- `python validate.py --compare` passed, including evaluation/method import separation and checks that evaluation reads generated artifacts.

### [2026-06-06 06:35] - core_claim_plus
- Final verification removed unscored Pairwise All-to-All target entries from the official rubric, keeping `TARGETS.md`, `EXPERIMENTS.md`, `reference.json`, and `scores.json` aligned.
- Generalized the main evaluator to discover result artifacts under `checkpoints/` instead of loading only fixed baseline/SWOT paths.
- Re-ran standalone evaluation and validation after the cleanup; both passed.

</details>

### Iteration 9: gpt-5.5 (verifier)
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 13m | **GPU**: 0.0h
- **Jobs**: 4 total (4 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-06 01:35] - core_claim
- Managed CPU job ran `scripts/reproduce.sh` successfully.
- Reproduced the paper's Fig. 5 Rabenseifner AllReduce example: Strawman-ICR 1500 us, SWOT 1200 us, 20% CCT reduction, valid schedule.

### [2026-06-06 05:48] - core_claim
- Added two paper Fig. 8 AllReduce scalability targets to the benchmark plan.
- Fixed evaluator artifact merging so `eval/` independently validates generated schedules from their workload specs.
- Tightened topology-bypass consistency so repeated use of the same plane/configuration cannot report a redundant reconfiguration.

### [2026-06-06 05:58] - core_claim_plus
- Managed CPU job `f4fb2013-489` regenerated all registered baseline and SWOT artifacts in the container.
- Reproduced Fig. 5 exactly: Strawman-ICR 1500 us, SWOT 1200 us, 20.0% CCT reduction, valid schedule.
- Reproduced the same claim on two Fig. 8 scalability settings with valid schedules: 64-node AllReduce reduction 35.89% versus the paper's 39.6%, and 512-node AllReduce reduction 42.09% versus the paper's 46.9%.
- `python validate.py --compare` passed, including evaluation/method import separation and checks that evaluation reads generated artifacts.

### [2026-06-06 06:35] - core_claim_plus
- Final verification removed unscored Pairwise All-to-All target entries from the official rubric, keeping `TARGETS.md`, `EXPERIMENTS.md`, `reference.json`, and `scores.json` aligned.
- Generalized the main evaluator to discover result artifacts under `checkpoints/` instead of loading only fixed baseline/SWOT paths.
- Re-ran standalone evaluation and validation after the cleanup; both passed.

</details>

### Iteration 10: gpt-6.1-sol (redteam)
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 8m | **GPU**: 0.0h
- **Jobs**: 6 total (5 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-06 01:35] - core_claim
- Managed CPU job ran `scripts/reproduce.sh` successfully.
- Reproduced the paper's Fig. 5 Rabenseifner AllReduce example: Strawman-ICR 1500 us, SWOT 1200 us, 20% CCT reduction, valid schedule.

### [2026-06-06 05:48] - core_claim
- Added two paper Fig. 8 AllReduce scalability targets to the benchmark plan.
- Fixed evaluator artifact merging so `eval/` independently validates generated schedules from their workload specs.
- Tightened topology-bypass consistency so repeated use of the same plane/configuration cannot report a redundant reconfiguration.

### [2026-06-06 05:58] - core_claim_plus
- Managed CPU job `f4fb2013-489` regenerated all registered baseline and SWOT artifacts in the container.
- Reproduced Fig. 5 exactly: Strawman-ICR 1500 us, SWOT 1200 us, 20.0% CCT reduction, valid schedule.
- Reproduced the same claim on two Fig. 8 scalability settings with valid schedules: 64-node AllReduce reduction 35.89% versus the paper's 39.6%, and 512-node AllReduce reduction 42.09% versus the paper's 46.9%.
- `python validate.py --compare` passed, including evaluation/method import separation and checks that evaluation reads generated artifacts.

### [2026-06-06 06:35] - core_claim_plus
- Final verification removed unscored Pairwise All-to-All target entries from the official rubric, keeping `TARGETS.md`, `EXPERIMENTS.md`, `reference.json`, and `scores.json` aligned.
- Generalized the main evaluator to discover result artifacts under `checkpoints/` instead of loading only fixed baseline/SWOT paths.
- Re-ran standalone evaluation and validation after the cleanup; both passed.

</details>

### Iteration 11: claude-opus-5-5 (hardener)
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 41m | **GPU**: 0.0h
- **Jobs**: 9 total (6 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-06 01:35] - core_claim
- Managed CPU job ran `scripts/reproduce.sh` successfully.
- Reproduced the paper's Fig. 5 Rabenseifner AllReduce example: Strawman-ICR 1500 us, SWOT 1200 us, 20% CCT reduction, valid schedule.

### [2026-06-06 05:48] - core_claim
- Added two paper Fig. 8 AllReduce scalability targets to the benchmark plan.
- Fixed evaluator artifact merging so `eval/` independently validates generated schedules from their workload specs.
- Tightened topology-bypass consistency so repeated use of the same plane/configuration cannot report a redundant reconfiguration.

### [2026-06-06 05:58] - core_claim_plus
- Managed CPU job `f4fb2013-489` regenerated all registered baseline and SWOT artifacts in the container.
- Reproduced Fig. 5 exactly: Strawman-ICR 1500 us, SWOT 1200 us, 20.0% CCT reduction, valid schedule.
- Reproduced the same claim on two Fig. 8 scalability settings with valid schedules: 64-node AllReduce reduction 35.89% versus the paper's 39.6%, and 512-node AllReduce reduction 42.09% versus the paper's 46.9%.
- `python validate.py --compare` passed, including evaluation/method import separation and checks that evaluation reads generated artifacts.

### [2026-06-06 06:35] - core_claim_plus
- Final verification removed unscored Pairwise All-to-All target entries from the official rubric, keeping `TARGETS.md`, `EXPERIMENTS.md`, `reference.json`, and `scores.json` aligned.
- Generalized the main evaluator to discover result artifacts under `checkpoints/` instead of loading only fixed baseline/SWOT paths.
- Re-ran standalone evaluation and validation after the cleanup; both passed.

### [2026-11-12] - core_claim_plus
- Hardening: the hidden test now runs solvers on held-out instances from the paper's Figs. 7-8 and Section 4.3 settings. It validates schedules physically and rewards better schedulers above seed noise.
- The reference (the paper's MILP, tight valid big-M, 120 s CBC) beats Strawman-ICR in every family. Fig. 5 reproduces exactly (1500 -> 1200 us).

</details>

### Iteration 11: claude-opus-5-5 (hardener)
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 1.9h | **GPU**: 0.0h
- **Jobs**: 16 total (8 completed, 2 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-06 01:35] - core_claim
- Managed CPU job ran `scripts/reproduce.sh` successfully.
- Reproduced the paper's Fig. 5 Rabenseifner AllReduce example: Strawman-ICR 1500 us, SWOT 1200 us, 20% CCT reduction, valid schedule.

### [2026-06-06 05:48] - core_claim
- Added two paper Fig. 8 AllReduce scalability targets to the benchmark plan.
- Fixed evaluator artifact merging so `eval/` independently validates generated schedules from their workload specs.
- Tightened topology-bypass consistency so repeated use of the same plane/configuration cannot report a redundant reconfiguration.

### [2026-06-06 05:58] - core_claim_plus
- Managed CPU job `f4fb2013-489` regenerated all registered baseline and SWOT artifacts in the container.
- Reproduced Fig. 5 exactly: Strawman-ICR 1500 us, SWOT 1200 us, 20.0% CCT reduction, valid schedule.
- Reproduced the same claim on two Fig. 8 scalability settings with valid schedules: 64-node AllReduce reduction 35.89% versus the paper's 39.6%, and 512-node AllReduce reduction 42.09% versus the paper's 46.9%.
- `python validate.py --compare` passed, including evaluation/method import separation and checks that evaluation reads generated artifacts.

### [2026-06-06 06:35] - core_claim_plus
- Final verification removed unscored Pairwise All-to-All target entries from the official rubric, keeping `TARGETS.md`, `EXPERIMENTS.md`, `reference.json`, and `scores.json` aligned.
- Generalized the main evaluator to discover result artifacts under `checkpoints/` instead of loading only fixed baseline/SWOT paths.
- Re-ran standalone evaluation and validation after the cleanup; both passed.

### [2026-11-12] - core_claim_plus
- Hardening: the hidden test now runs solvers on held-out instances from the paper's Figs. 7-8 and Section 4.3 settings. It validates schedules physically and rewards better schedulers above seed noise.
- The reference (the paper's MILP, tight valid big-M, 120 s CBC) beats Strawman-ICR in every family. Fig. 5 reproduces exactly (1500 -> 1200 us).

### [2026-11-14] - core_claim_plus
- Hardening iteration 12. The evaluator counts a 120 CPU-second budget per instance over the solver's process tree, replacing the wall-clock limit. The reference MILP uses a deterministic CBC node budget and is bit-repeatable across nodes.
- The test was scaled to 34 stratified instances per slice, restricted to settings where a 15-line relay rule does not match the paper's method.
- Hidden-test reference: 32.08 / 26.88 / 24.29%. A hybrid positive control scores 45.62 / 40.33 / 34.57%: +12.4 points paired, 30 wins and 0 losses, against 1-2.4 points of seed noise.
- Fig. 5 reproduces exactly (1500 -> 1200 us). Fig. 8: 38.2% at 64 nodes (paper 39.6%) and 41.6% at 512 nodes (paper 46.9%).

</details>

### Iteration 11: claude-opus-5-5 (hardener)
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 29m | **GPU**: 0.0h
- **Jobs**: 20 total (9 completed, 3 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-06 01:35] - core_claim
- Managed CPU job ran `scripts/reproduce.sh` successfully.
- Reproduced the paper's Fig. 5 Rabenseifner AllReduce example: Strawman-ICR 1500 us, SWOT 1200 us, 20% CCT reduction, valid schedule.

### [2026-06-06 05:48] - core_claim
- Added two paper Fig. 8 AllReduce scalability targets to the benchmark plan.
- Fixed evaluator artifact merging so `eval/` independently validates generated schedules from their workload specs.
- Tightened topology-bypass consistency so repeated use of the same plane/configuration cannot report a redundant reconfiguration.

### [2026-06-06 05:58] - core_claim_plus
- Managed CPU job `f4fb2013-489` regenerated all registered baseline and SWOT artifacts in the container.
- Reproduced Fig. 5 exactly: Strawman-ICR 1500 us, SWOT 1200 us, 20.0% CCT reduction, valid schedule.
- Reproduced the same claim on two Fig. 8 scalability settings with valid schedules: 64-node AllReduce reduction 35.89% versus the paper's 39.6%, and 512-node AllReduce reduction 42.09% versus the paper's 46.9%.
- `python validate.py --compare` passed, including evaluation/method import separation and checks that evaluation reads generated artifacts.

### [2026-06-06 06:35] - core_claim_plus
- Final verification removed unscored Pairwise All-to-All target entries from the official rubric, keeping `TARGETS.md`, `EXPERIMENTS.md`, `reference.json`, and `scores.json` aligned.
- Generalized the main evaluator to discover result artifacts under `checkpoints/` instead of loading only fixed baseline/SWOT paths.
- Re-ran standalone evaluation and validation after the cleanup; both passed.

### [2026-11-12] - core_claim_plus
- Hardening: the hidden test now runs solvers on held-out instances from the paper's Figs. 7-8 and Section 4.3 settings. It validates schedules physically and rewards better schedulers above seed noise.
- The reference (the paper's MILP, tight valid big-M, 120 s CBC) beats Strawman-ICR in every family. Fig. 5 reproduces exactly (1500 -> 1200 us).

### [2026-11-14] - core_claim_plus
- Hardening iteration 12. The evaluator counts a 120 CPU-second budget per instance over the solver's process tree, replacing the wall-clock limit. The reference MILP uses a deterministic CBC node budget and is bit-repeatable across nodes.
- The test was scaled to 34 stratified instances per slice, restricted to settings where a 15-line relay rule does not match the paper's method.
- Hidden-test reference: 32.08 / 26.88 / 24.29%. A hybrid positive control scores 45.62 / 40.33 / 34.57%: +12.4 points paired, 30 wins and 0 losses, against 1-2.4 points of seed noise.
- Fig. 5 reproduces exactly (1500 -> 1200 us). Fig. 8: 38.2% at 64 nodes (paper 39.6%) and 41.6% at 512 nodes (paper 46.9%).

### [2026-11-14] - core_claim_plus (iteration 13 hardening)
- The reference MILP's CBC no longer sees any time limit (node budget only, CPU-time mode, kill switch outside CBC); PuLP pinned to 3.3.2. Two independent hidden-test runs, each run alone, are identical: 32.08 / 26.87 / 25.39 (Fig. 5: 1500 -> 1200 us exactly).
- Positive control +11.8 +- 1.5 points over the reference (30/0 instances), CBC seed noise +1.1 to +1.5; relay rule below the reference in every family after the Pairwise k=4 hardware cell became ReduceScatter. Details in HARDENING.md.

</details>


---

# Reproduction Milestones

**Current: core_claim_plus**

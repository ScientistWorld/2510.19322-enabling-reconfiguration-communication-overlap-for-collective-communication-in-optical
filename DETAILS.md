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

Instances come from the collective algorithms and network settings of the source paper's evaluation (see `data/collectives.py` for generators): Rabenseifner ReduceScatter / AllReduce (recursive halving/doubling), Bruck All-to-All and Pairwise-exchange All-to-All, on 9-1024 nodes, with `k` in {2, 4, 8}, payloads of 1-512 MB, `T_lat` = 20 us and `T_recfg` from 20 us to 20 ms. Public train instances are in `eval/train/instances.json`; held-out test instances are drawn from the same families and ranges.

## Why It Matters

Distributed ML training spends substantial time in collective communication. Optical circuit switches provide high bandwidth, but a fixed topology cannot serve dynamic communication patterns with limited optical degree, and naively switching every plane at every step adds the switching delay to the critical path.

## Success Criteria

Valid schedules with lower CCT than the naive lockstep reconfiguration baseline (all planes serve every step with an even split and switch together whenever the topology changes), under fixed optical resources, bandwidth, latencies and collective workload, produced within a fixed per-instance compute budget.

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

- The paper's MILP (Eqs. 1-11): the `last_cfg`/`s_ij` logic is linearized with pairwise "most recent previous use" implications. A plane's first use is free (planes are pre-configured), as in the paper's Fig. 5.
- Solved with CBC via PuLP under the paper's 120 s limit, single thread, fixed CBC seeds.
- The paper leaves the big-M constant unspecified. The reproduction uses the lockstep (Strawman-ICR) completion time as M and bounds the CCT by it. The lockstep schedule is feasible, so the MILP optimum is unchanged. Earlier iterations used a loose horizon M, which let the time-limited incumbent end up worse than lockstep on some large k=8 instances (`--big-m horizon` keeps that variant).
- The MILP's plane-use/split decisions are written with exact earliest-start timing. If CBC returns no incumbent, the lockstep schedule is written.

## Main Claims

The primary claim is that demand-aware overlapping schedules reduce CCT compared with naive intra-collective reconfiguration and static optical scheduling while preserving collective correctness. The paper reports a 20% reduction in its 8-node design-intuition example and peak reductions up to 89.7% across larger simulated collective workloads.

---

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


---

# Reproduction Milestones

**Current: core_claim_plus**

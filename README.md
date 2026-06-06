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

How can a scheduler minimize collective-communication completion time in an optical circuit switched cluster when collective algorithms require a sequence of changing pairwise communication topologies?

The benchmark considers `p` compute nodes connected by `k` optical planes. A collective operation is represented as ordered communication steps. Each step has a required topology/configuration and a message volume. A valid schedule must transfer every step's full message volume while respecting optical circuit setup time, per-plane serial resource use, and the sequential barriers of the collective algorithm.

## Why It Matters

Distributed ML training spends substantial time in collective communication. Optical circuit switches can provide high bandwidth, but static topologies underuse links for dynamic communication patterns and naive per-step reconfiguration can add prohibitive switching delay.

## Success Criteria

A successful system produces valid execution schedules with lower communication completion time than static or naive dynamic baselines under fixed optical resources, bandwidth, latency, and collective workload.

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

## Main Claims

The primary claim is that demand-aware overlapping schedules reduce CCT compared with naive intra-collective reconfiguration and static optical scheduling while preserving collective correctness. The paper reports a 20% reduction in its 8-node design-intuition example and peak reductions up to 89.7% across larger simulated collective workloads.

---

# Evaluation

## Metrics

- `cct_us`: communication completion time in microseconds. Lower is better.
- `cct_reduction_vs_strawman_pct`: percent CCT reduction relative to the naive intra-collective reconfiguration baseline. Higher is better.
- `valid_schedule`: 1 if the schedule satisfies traffic conservation, circuit readiness, per-plane serial use, and collective step barriers; 0 otherwise. Higher is better.
- `reconfiguration_events`: number of topology reconfigurations scheduled across optical planes. Lower is better when CCT is comparable.

## Baselines and Targets

The primary baseline is naive intra-collective reconfiguration: all optical planes serve each collective step in lockstep with an even message split, and the system pays one global reconfiguration delay between adjacent steps requiring different topologies.

The core target is the paper's 8-node Rabenseifner AllReduce example with two 400 Gbps optical planes, 200 us reconfiguration latency, 40 MB payload, and no base latency in the illustrated timing model. The paper reports 1500 us CCT for the naive baseline, 1200 us CCT for the optimized schedule, and 20% CCT reduction.

The expanded scalability targets use the paper's Rabenseifner AllReduce setup from Fig. 8 with `k=4`, 200 Gbps per link, 32 MB messages, 20 us base latency, and 200 us reconfiguration latency. The paper reports CCT reductions over the naive baseline of 39.6% at 64 nodes and 46.9% at 512 nodes.

## Evaluation Protocol

Run `scripts/reproduce.sh` to generate baseline and scheduler artifacts under `checkpoints/`, then run `scripts/evaluate.sh` to write `scoring/scores.json`. Evaluation code reads only artifacts and code under `eval/`; it does not import the proposed method implementation.

All comparisons must use the same collective step sequence, optical degree, per-link bandwidth, base latency, and reconfiguration latency. Do not compare methods that alter the collective semantics or add optical planes/bandwidth.

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


---

# Reproduction Milestones

**Current: core_claim_plus**

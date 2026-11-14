# Evaluation Targets

Every scored experiment reports, per method, a benefit metric and a constraint metric, both recomputed by the evaluator from the serialized schedules:

- **Benefit**: `cct_reduction_vs_strawman_pct` (primary, higher is better). This is the mean over the experiment's instances of the full-collective CCT reduction versus the evaluator-computed lockstep Strawman-ICR schedule, with each instance clipped to [-100, 100].
- **Constraint**: `valid_schedule` (higher is better). It is 1 only if every instance of every experiment received a physically valid schedule within the 120 CPU-second budget. Otherwise the run fails, and every metric of every experiment gets its worst value (-100 / 0).

How to run: `bash scripts/evaluate_train.sh` (visible), `bash scripts/evaluate_test.sh` (held out). Both take no arguments and score every `scripts/solvers/*.sh` plus the required `swot`.

The reference numbers below are the reproduced paper method (the SWOT MILP with CBC under a deterministic node budget); they are identical on every run.

## Primary: allreduce_scaling (weight 0.40)

Rabenseifner AllReduce on 64-1024 nodes, k=4 planes at 200 Gbps, 16-64 MB payloads, 20 us base latency, 200 us switching; switching share 0.35-0.80. Paper anchor: 39.6% (64 nodes) to 46.9% (512 nodes) at 32 MB. Reference reproduction: 32.08% (hidden test), 33.40% (train).

## high_optical_degree (weight 0.30)

Rabenseifner ReduceScatter on 128-1024 nodes, k=8 at 100 Gbps, 1-512 MB payloads, 200 us switching; switching share 0.35-0.92. Paper anchor: 46.9% (its only non-peak Rabenseifner number, AllReduce at k=4); the Fig. 7 k=8 peaks (85.4-89.1%) are kept under `_` keys. Reference reproduction: 26.88% (hidden test), 25.12% (train).

## hardware_sensitivity (weight 0.30)

Every combination of k in {2,4,8} (800/k Gbps) and switching latency in {0.02, 0.2, 2, 20} ms once: all four algorithms at k=2 (256 nodes, Pairwise on 9 or 17), no Bruck at k=4, ReduceScatter at k=8; 0.25-8192 MB payloads around the transmission/switching knee (switching share 0.35-0.92). Paper anchor: 46.9% (Fig. 8(a) AllReduce at k=4, 0.2 ms switching, 512 nodes; Section 4.3 itself gives no numbers); the k=2 design example (20%) is kept under a `_` key. Reference reproduction: 24.29% (hidden test), 25.26% (train).

## Unscored paper checks (`scoring/scores.json`, via `bash scripts/evaluate.sh`)

`_paper_fig5_rabenseifner_allreduce_8node` (paper: 1500 -> 1200 us, 20%; reproduced exactly), `_paper_fig8_rabenseifner_allreduce_64node_k4` (paper: 39.6%; reproduced 38.2%) and `_paper_fig8_rabenseifner_allreduce_512node_k4` (paper: 46.9%; reproduced 41.6%).

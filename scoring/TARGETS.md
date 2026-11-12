# Evaluation Targets

Every scored experiment reports, per method, a benefit metric and a constraint metric, both recomputed by the evaluator from the serialized schedules:

- **Benefit**: `cct_reduction_vs_strawman_pct` (primary, higher is better). This is the mean over the experiment's instances of the full-collective CCT reduction versus the evaluator-computed lockstep Strawman-ICR schedule, with each instance clipped to [-100, 100].
- **Constraint**: `valid_schedule` (higher is better). It is 1 only if every instance of every experiment received a physically valid schedule within the time limit. Otherwise the run fails, and every metric of every experiment gets its worst value (-100 / 0).

How to run: `bash scripts/evaluate_train.sh` (visible), `bash scripts/evaluate_test.sh` (held out). Both take no arguments and score every `scripts/solvers/*.sh` plus the required `swot`.

## Primary: allreduce_scaling (weight 0.40)

Rabenseifner AllReduce on 64-1024 nodes, k=4 planes at 200 Gbps, 16-64 MB payloads, 20 us base latency, 200 us switching. Paper anchor: 39.6% (64 nodes) to 46.9% (512 nodes) at 32 MB. Reference reproduction (hidden test): 37.93%.

## collective_algorithms (weight 0.40)

Rabenseifner ReduceScatter/AllReduce and Bruck All-to-All on 128-512 nodes, Pairwise All-to-All on 9-12 nodes, k=8 at 100 Gbps, 1-512 MB payloads. Paper anchor: peak reductions of 85.4-89.1% (peaks, not means). Reference reproduction (hidden test): 46.93%.

## hardware_sensitivity (weight 0.20)

256-node Rabenseifner/Bruck collectives and 9- or 17-node Pairwise All-to-All, with k in {2,4,8} at 800/k Gbps and switching latency in {0.02, 0.2, 2, 20} ms, 1-256 MB payloads. Paper anchor: the k=2 design example, 20% (1500 -> 1200 us). Reference reproduction (hidden test): 43.71%.

## Unscored paper checks (`scoring/scores.json`, via `bash scripts/evaluate.sh`)

`_paper_fig5_rabenseifner_allreduce_8node` (paper: 1500 -> 1200 us, 20%), `_paper_fig8_rabenseifner_allreduce_64node_k4` (paper: 39.6%) and `_paper_fig8_rabenseifner_allreduce_512node_k4` (paper: 46.9%).

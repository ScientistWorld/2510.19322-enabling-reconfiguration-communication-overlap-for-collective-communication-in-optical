# Evaluation Targets

## Primary: fig5_rabenseifner_allreduce_8node

Tests whether a scheduler reduces communication completion time on the paper's central design-intuition example while preserving the collective communication ordering constraints.

- **Metric**: `cct_us` (lower is better)
- **Benefit metric**: `cct_reduction_vs_strawman_pct` (higher is better)
- **Constraint metric**: `valid_schedule` (higher is better; invalid schedules fail the benchmark regardless of CCT)
- **How to run**: `bash scripts/reproduce.sh`, then inspect `scoring/scores.json`

## Expansion: fig8_rabenseifner_allreduce_64node_k4

Tests whether the same evaluation surface remains useful at the smaller scalability point reported in the paper's Fig. 8 AllReduce experiment.

- **Metric**: `cct_us` (lower is better)
- **Benefit metric**: `cct_reduction_vs_strawman_pct` (higher is better)
- **Constraint metric**: `valid_schedule` (higher is better)
- **How to run**: `bash scripts/reproduce.sh`, then inspect `scoring/scores.json`

## Expansion: fig8_rabenseifner_allreduce_512node_k4

Tests whether the same evaluation surface remains useful at the larger scalability point reported in the paper's Fig. 8 AllReduce experiment.

- **Metric**: `cct_us` (lower is better)
- **Benefit metric**: `cct_reduction_vs_strawman_pct` (higher is better)
- **Constraint metric**: `valid_schedule` (higher is better)
- **How to run**: `bash scripts/reproduce.sh`, then inspect `scoring/scores.json`

## Expansion: fig8_pairwise_alltoall_5node_k4

Tests whether the scheduler handles the denser dynamic topology sequence from the paper's Pairwise All-to-All scalability experiment.

- **Metric**: `cct_us` (lower is better)
- **Benefit metric**: `cct_reduction_vs_strawman_pct` (higher is better)
- **Constraint metric**: `valid_schedule` (higher is better)
- **How to run**: `bash scripts/reproduce.sh`, then inspect `scoring/scores.json`

## Expansion: fig8_pairwise_alltoall_10node_k4

Tests whether the Pairwise All-to-All target remains useful as the number of ordered communication stages grows beyond the one-shot capacity discussed in the paper.

- **Metric**: `cct_us` (lower is better)
- **Benefit metric**: `cct_reduction_vs_strawman_pct` (higher is better)
- **Constraint metric**: `valid_schedule` (higher is better)
- **How to run**: `bash scripts/reproduce.sh`, then inspect `scoring/scores.json`

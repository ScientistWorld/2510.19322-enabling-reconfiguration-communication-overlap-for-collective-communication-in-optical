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

## Secondary: fig8_pairwise_alltoall_5node_k4

Tests the paper's Fig. 8 Pairwise All-to-All scalability setting at the smallest node count where the paper reports SWOT's advantage over naive intra-collective reconfiguration.

- **Metric**: `cct_us` (lower is better)
- **Benefit metric**: `cct_reduction_vs_strawman_pct` (higher is better)
- **Constraint metric**: `valid_schedule` (higher is better)
- **How to run**: `bash scripts/reproduce.sh`, then inspect `scoring/scores.json`

## Secondary: fig8_pairwise_alltoall_10node_k4

Tests the paper's Fig. 8 Pairwise All-to-All scalability setting at the larger node count reported in the paper's scalability summary.

- **Metric**: `cct_us` (lower is better)
- **Benefit metric**: `cct_reduction_vs_strawman_pct` (higher is better)
- **Constraint metric**: `valid_schedule` (higher is better)
- **How to run**: `bash scripts/reproduce.sh`, then inspect `scoring/scores.json`

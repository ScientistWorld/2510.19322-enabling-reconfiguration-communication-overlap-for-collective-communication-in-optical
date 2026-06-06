# Evaluation Targets

## Primary: fig5_rabenseifner_allreduce_8node

Tests whether a scheduler reduces communication completion time on the paper's central design-intuition example while preserving the collective communication ordering constraints.

- **Metric**: `cct_us` (lower is better)
- **Benefit metric**: `cct_reduction_vs_strawman_pct` (higher is better)
- **Constraint metric**: `valid_schedule` (higher is better; invalid schedules fail the benchmark regardless of CCT)
- **How to run**: `bash scripts/reproduce.sh`, then inspect `scoring/scores.json`

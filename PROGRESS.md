# Progress

## What Works

- Paper analysis completed from the markdown.
- The benchmark is structured around deterministic collective-communication simulations; no external dataset is required.
- Implemented workload definitions in `data/collectives.py`.
- Implemented the paper baseline `strawman_icr` in `baseline/simulate_baselines.py`.
- Implemented the SWOT MILP scheduler in `method/swot_scheduler.py`.
- Implemented method-agnostic evaluation in `eval/evaluate_results.py`; it now independently validates schedule artifacts instead of trusting method-reported validity.
- Current verified milestone is `core_claim`.

## Results

- Managed CPU job `7126c74f-64d` completed successfully.
- `scripts/reproduce.sh` ran the strawman ICR baseline, the SWOT MILP scheduler, and the independent evaluator.
- Reproduced Fig. 5 target:
  - `strawman_icr`: `cct_us = 1500.0`, `valid_schedule = 1.0`, `cct_reduction_vs_strawman_pct = 0.0`
  - `swot`: `cct_us = 1200.0`, `valid_schedule = 1.0`, `cct_reduction_vs_strawman_pct = 20.0`
- `python validate.py --compare` passed, including import-separation checks and confirmation that `eval/` reads generated method outputs.
- Continuation audit on 2026-06-06 re-ran standalone `scripts/evaluate.sh` followed by `python validate.py --compare`; both completed successfully with the same reproduced scores.

## Remaining

- Higher milestones would require adding more paper figures and scenarios beyond the minimum Fig. 5 core claim.
- The reusable environment is complete for the current target: `scripts/reproduce.sh` regenerates artifacts and `scripts/evaluate.sh` scores them.

## Issues

- The external job log path supplied by the scheduler was not readable from this shell, but the generated workspace artifacts were present and validated.
- No blocking issues remain for the core claim.
- Continuation audit found no implementation, evaluation, or deliverable issues requiring code changes.

## Deviations from Paper

- The core reference experiment exactly follows the paper's Fig. 5 illustrative timing setup.
- A 16-node scaled workload factory is available in `data/collectives.py` for future extension, but default scoring is restricted to the paper-reported Fig. 5 target.

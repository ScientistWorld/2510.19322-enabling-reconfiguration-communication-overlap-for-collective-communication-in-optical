# Progress

## What Works

- Paper analysis completed from the markdown.
- The benchmark is structured around deterministic collective-communication simulations; no external dataset is required.
- Implemented workload definitions in `data/collectives.py`.
- Implemented the paper baseline `strawman_icr` in `baseline/simulate_baselines.py`.
- Implemented the SWOT MILP scheduler in `method/swot_scheduler.py`.
- Implemented method-agnostic evaluation in `eval/evaluate_results.py`; it now independently validates schedule artifacts instead of trusting method-reported validity.
- Current verified milestone is `core_claim`.
- Added two Fig. 8 Rabenseifner AllReduce scalability settings to the registered workload suite for the next managed CPU run.
- Fixed evaluator artifact merging so workload specs are preserved and schedule validity is recomputed by `eval/`.
- Tightened MILP and evaluator transition checks so topology bypassing does not report redundant reconfigurations when a plane's last used configuration already matches the current step.

## Results

- Managed CPU job `7126c74f-64d` completed successfully.
- `scripts/reproduce.sh` ran the strawman ICR baseline, the SWOT MILP scheduler, and the independent evaluator.
- Reproduced Fig. 5 target:
  - `strawman_icr`: `cct_us = 1500.0`, `valid_schedule = 1.0`, `cct_reduction_vs_strawman_pct = 0.0`
  - `swot`: `cct_us = 1200.0`, `valid_schedule = 1.0`, `cct_reduction_vs_strawman_pct = 20.0`
- `python validate.py --compare` passed, including import-separation checks and confirmation that `eval/` reads generated method outputs.
- Continuation audit on 2026-06-06 re-ran standalone `scripts/evaluate.sh` followed by `python validate.py --compare`; both completed successfully with the same reproduced scores.
- Local lightweight validation after the expansion edits passed: `python validate.py --compare` and Python syntax checks. The expanded scores still need to be regenerated in a managed CPU job because PuLP is installed through the container setup, not on the login node.

## Remaining

- The pending managed CPU job will regenerate scores for the added Fig. 8 scalability targets. If successful and the additional settings support the same CCT-reduction claim with valid schedules, the workspace can be advanced to `core_claim_plus`.
- Higher milestones would require adding more paper figures and scenarios beyond the current AllReduce examples.
- The reusable environment is complete for the current target: `scripts/reproduce.sh` regenerates artifacts and `scripts/evaluate.sh` scores them.

## Issues

- The external job log path supplied by the scheduler was not readable from this shell, but the generated workspace artifacts were present and validated.
- No blocking issues remain for the core claim.
- Continuation audit found no implementation, evaluation, or deliverable issues requiring code changes.
- A subagent audit found that the previous evaluator dropped `spec` during artifact merging, which meant independent validation was bypassed. This has been fixed before the expansion submission.
- The same audit found redundant reconfiguration flags in the previous Fig. 5 artifact. The MILP and evaluator now enforce transition consistency; the next job will regenerate artifacts under the stricter rules.

## Deviations from Paper

- The core reference experiment exactly follows the paper's Fig. 5 illustrative timing setup.
- The Fig. 8 scalability targets reproduce the paper's Rabenseifner AllReduce node-count settings, but this reproduction still uses the aggregate per-step configuration model rather than explicit per-node OCS permutation matrices.

# Progress

## What Works

- Paper analysis completed from the markdown.
- The benchmark is structured around deterministic collective-communication simulations; no external dataset is required.
- Implemented workload definitions in `data/collectives.py`.
- Implemented the paper baseline `strawman_icr` in `baseline/simulate_baselines.py`.
- Implemented the SWOT MILP scheduler in `method/swot_scheduler.py`.
- Implemented method-agnostic evaluation in `eval/evaluate_results.py`; it now independently validates schedule artifacts instead of trusting method-reported validity.
- Current verified milestone is `core_claim_plus`.
- Added two Fig. 8 Rabenseifner AllReduce scalability settings to the registered workload suite and regenerated their scores in a managed CPU run.
- Fixed evaluator artifact merging so workload specs are preserved and schedule validity is recomputed by `eval/`.
- Tightened MILP and evaluator transition checks so topology bypassing does not report redundant reconfigurations when a plane's last used configuration already matches the current step.
- Tightened `scores.json` generation so it emits schedule constraint diagnostics and penalizes invalid non-baseline artifacts instead of trusting self-reported validity.

## Results

- Managed CPU job `7126c74f-64d` completed successfully.
- `scripts/reproduce.sh` ran the strawman ICR baseline, the SWOT MILP scheduler, and the independent evaluator.
- Reproduced Fig. 5 target:
  - `strawman_icr`: `cct_us = 1500.0`, `valid_schedule = 1.0`, `cct_reduction_vs_strawman_pct = 0.0`
  - `swot`: `cct_us = 1200.0`, `valid_schedule = 1.0`, `cct_reduction_vs_strawman_pct = 20.0`
- `python validate.py --compare` passed, including import-separation checks and confirmation that `eval/` reads generated method outputs.
- Continuation audit on 2026-06-06 re-ran standalone `scripts/evaluate.sh` followed by `python validate.py --compare`; both completed successfully with the same reproduced scores.
- Local lightweight validation after the expansion edits passed: `python validate.py --compare` and Python syntax checks.
- Managed CPU job `f4fb2013-489` regenerated expanded artifacts and passed `python validate.py --compare`.
- Reproduced Fig. 8 scalability targets:
  - `fig8_rabenseifner_allreduce_64node_k4`: Strawman-ICR `cct_us = 2870.0`, SWOT `cct_us = 1840.0`, SWOT reduction `35.8885%`, valid schedule. Paper reports `39.6%`.
  - `fig8_rabenseifner_allreduce_512node_k4`: Strawman-ICR `cct_us = 4198.75`, SWOT `cct_us = 2431.6667`, SWOT reduction `42.0859%`, valid schedule. Paper reports `46.9%`.
- Final verification re-ran standalone `scripts/evaluate.sh`, `scripts/evaluate_train.sh`, `scripts/evaluate_test.sh`, and `python validate.py --compare`; all completed successfully.

## Remaining

- Higher milestones would require adding more paper figures and scenarios beyond the current AllReduce suite, such as Pairwise All-to-All, Bruck All-to-All, topology/OCS-count sweeps, and additional baselines.
- The reusable environment is complete for the current target: `scripts/reproduce.sh` regenerates artifacts and `scripts/evaluate.sh` scores them.
- `scoring/scores.json` contains every experiment listed in `scoring/TARGETS.md`.

## Issues

- The original external scheduler log path was not readable from this shell, but the local copies under `/home/user/jobs/` were available and reviewed.
- No blocking issues remain for the core or expanded AllReduce claims.
- Continuation audit found no implementation, evaluation, or deliverable issues requiring code changes.
- A subagent audit found that the previous evaluator dropped `spec` during artifact merging, which meant independent validation was bypassed. This has been fixed before the expansion submission.
- The same audit found redundant reconfiguration flags in the previous Fig. 5 artifact. The MILP and evaluator now enforce transition consistency, and job `f4fb2013-489` regenerated artifacts under the stricter rules.

## Deviations from Paper

- The core reference experiment exactly follows the paper's Fig. 5 illustrative timing setup.
- The Fig. 8 scalability targets reproduce the paper's Rabenseifner AllReduce node-count settings, but this reproduction still uses the aggregate per-step configuration model rather than explicit per-node OCS permutation matrices.

## Iteration 11 (hardening)

- **Problem found.** The hidden test trusted method-written numbers, a mutable baseline and a mutable spec, and scored a public suffix slice. Shortcuts outranked the reference, and a genuinely better solver was within seed noise (`REDTEAM.md`).
- **Redesign.** Methods are solvers run by the evaluator on held-out instances, with strict physical validation, an evaluator-computed baseline, full-collective CCT, and failure of the whole run on any bad instance. Scored experiments are three families from the paper's Figs. 7-8 and Section 4.3.
- **Reference fix.** The paper's MILP now uses a valid tight big-M (the lockstep CCT); the loose horizon M had produced worse-than-lockstep schedules.
- **Hidden-test reference.** 37.93 / 46.93 / 43.71% reduction vs Strawman-ICR.
  - The MILP+LNS positive control scores +5.7 ± 1.7 points paired (rank +0.36 vs seed noise 0.07).
  - Every redteam shortcut now fails or scores its true lockstep value.
  - A pure-Python local search outranks the reference about as much as the positive control does (see `HARDENING.md` §3).
- **Paper instances.** Fig. 5 1500 → 1200 us (exact); Fig. 8 38.4% at 64 nodes (paper 39.6%); 25.2% at 512 nodes in this run (paper 46.9%; time-limit variance, 41.6% on the identical train instance).

## Iteration 12 (hardening)

- **Review items.**
  - The annealing heuristic tied the positive control.
  - The hardware sweep separated weakly.
  - Results depended on a wall-clock CBC limit.
- **Budget.** CPU time is counted by the evaluator (subreaper over the solver's process tree). The reference uses a calibrated deterministic CBC node budget. CBC `timeMode cpu` was found to write unusable solutions on time-limited stops, so it is not used.
- **Test.** 34 instances per slice in three families, stratified over the switching share. Settings where a fixed relay rule matches the paper's MILP are unscored.
- **Results (hidden test).**
  - Reference: 32.08 / 26.88 / 24.29%.
  - Hybrid positive control: 45.62 / 40.33 / 34.57%.
  - Relay rule: 28.63 / 23.21 / 25.04%.
  - Seed noise: 1-2.4 points.
  - Every shortcut fails or scores lockstep.
  - Details in `HARDENING.md`.

## Iteration 13 (hardening)

- Reference: CBC gets no wall-clock or CPU time limit, only the deterministic node budget; CPU-time kill switch outside CBC as safety stop; `pulp==3.3.2` pinned. Reference reproduced bit-identically twice (and under full CPU load).
- REVIEW.md's "reference = hybrid" did not reproduce: the corrected reference equals the stored 32.08 / 26.87; the hybrid stays 13.5 / 13.5 / 8.8 points above.
- Three candidate families where the paper's solver falls short (k=8 AllReduce, AllReduce and ReduceScatter beyond 1024 nodes) were measured and dropped: a 15-line relay rule beats the reference there.
- `hardware_sensitivity`: Pairwise k=4 cell replaced by ReduceScatter (relay rule reached the best known schedule there); relay rule now below the reference in every family.
- Evaluators pre-write an all-failed score file, so a solver that kills the evaluator scores as failed.

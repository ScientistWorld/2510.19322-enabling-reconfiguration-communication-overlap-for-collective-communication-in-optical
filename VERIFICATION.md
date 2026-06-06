# Verification Report

## Initial Assessment

The workspace started from a justified `core_claim_plus` reproduction for the verified AllReduce scope. Fig. 5 matches the paper's reported 20.0% CCT reduction, and the two Fig. 8 Rabenseifner AllReduce scalability points reproduce the same claim with valid schedules and plausible gaps from the paper's reported reductions.

The main issue was a stale target expansion: Pairwise All-to-All experiments had been added to the official rubric and target documentation, but no matching entries existed in `scoring/scores.json`.

## Issues Found

- **critical**: `scoring/reference.json`, `scoring/TARGETS.md`, `scoring/EXPERIMENTS.md`, `scoring/CONSTRAINTS.md`, `briefing/evaluation.md`, and `data/collectives.py` listed two Pairwise All-to-All targets that were not present in `scoring/scores.json`. This would leave future scientist agents with phantom targets and a misleading rubric.
- **minor**: `scoring/scores.json` was stale relative to the stricter evaluator and did not include the schedule-diagnostic constraint metrics now declared in `reference.json`.
- **cosmetic**: unrelated pre-existing root changes remain in `README.md`, `manifest.json`, and ignored `trajectory/` files. They were not part of this verification and were left untouched.

## Fixes Applied

- Removed the unverified Pairwise All-to-All target entries from the active workload registry, reference rubric, target documentation, experiment overview, constraints checklist, evaluation briefing, and progress notes.
- Restored the official scoring weights over the three verified experiments: 0.5 for Fig. 5 and 0.25 for each Fig. 8 AllReduce scalability point.
- Re-ran artifact-only evaluation with `bash scripts/evaluate.sh`, `bash scripts/evaluate_train.sh`, and `bash scripts/evaluate_test.sh`.
- Re-ran `python validate.py --compare`; validation passed, including method/eval import separation, artifact-reading checks, train/test independence, method-key alignment, and shared-path checks.

## Final Judgment

The workspace is ready to serve as a research gym for the verified AllReduce scheduling scope. Problem/method separation is clean, evaluation reads serialized artifacts rather than method code, and the scored metrics include both benefit metrics and schedule-validity constraints.

- Milestone: core_claim_plus
- Ready for gym use: yes
- Confidence: high
- Key limitation: the Fig. 8 reproduction uses an aggregate per-step topology model rather than explicit per-node OCS permutation matrices.

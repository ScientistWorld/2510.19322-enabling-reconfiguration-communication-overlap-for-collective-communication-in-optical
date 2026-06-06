# Verification Report

## Initial Assessment

The workspace started from a justified `core_claim_plus` state for the verified AllReduce experiments: Fig. 5 reproduced the reported 20.0% CCT reduction exactly, and two Fig. 8 Rabenseifner AllReduce scalability points reproduced the same benefit/validity claim within a plausible gap from the paper.

One stale expansion was not ready for the final gym: Pairwise All-to-All targets had been added to `reference.json` and the target documentation, but no matching entries existed in `scores.json`.

## Issues Found

- **critical**: `TARGETS.md` and `reference.json` included two unscored Pairwise All-to-All targets. Future scientist agents are scored on `scores.json`, so leaving unscored targets in the official target list would make the gym documentation and rubric inconsistent.
- **minor**: the main evaluator loaded only two fixed artifact paths. It worked for the reproduced method, but was less reusable for future candidate methods that produce the same JSON artifact format under a different directory.
- **cosmetic**: generated cache and temporary audit files were present in the workspace.

## Fixes Applied

- Removed the unverified Pairwise All-to-All target entries from `data/collectives.py`, `scoring/reference.json`, `scoring/TARGETS.md`, `scoring/EXPERIMENTS.md`, `scoring/CONSTRAINTS.md`, `briefing/evaluation.md`, and `PROGRESS.md`.
- Restored official experiment weights over the three verified targets: 0.5 for Fig. 5, 0.25 for each Fig. 8 AllReduce scalability point.
- Generalized `eval/evaluate_results.py` to discover JSON result artifacts recursively under `checkpoints/`, while still remaining independent of `method/`.
- Removed local generated `__pycache__` directories and temporary audit JSON files under `tmp/`.
- Re-ran `bash scripts/evaluate.sh`, `bash scripts/evaluate_train.sh /home/user/checkpoints`, `bash scripts/evaluate_test.sh /home/user/checkpoints`, and `python validate.py --compare`; all checks passed.

## Final Judgment

The workspace is ready to serve as a research gym for the verified AllReduce scope. Problem/method separation is clean, evaluation reads method artifacts rather than regenerating experiments, and the scored experiments include both benefit (`cct_us`, `cct_reduction_vs_strawman_pct`) and constraint (`valid_schedule`) metrics.

- Milestone: core_claim_plus
- Ready for gym use: yes
- Confidence: high
- Key limitation: the expanded Fig. 8 reproduction uses an aggregate per-step topology model rather than explicit per-node OCS permutation matrices.

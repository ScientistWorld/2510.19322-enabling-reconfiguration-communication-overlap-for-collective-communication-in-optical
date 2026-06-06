# Reproduction Milestones

**Current: core_claim_plus**

## Progress Log

### [2026-06-06 01:35] - core_claim
- Managed CPU job ran `scripts/reproduce.sh` successfully.
- Reproduced the paper's Fig. 5 Rabenseifner AllReduce example: Strawman-ICR 1500 us, SWOT 1200 us, 20% CCT reduction, valid schedule.

### [2026-06-06 05:48] - core_claim
- Added two paper Fig. 8 AllReduce scalability targets to the benchmark plan.
- Fixed evaluator artifact merging so `eval/` independently validates generated schedules from their workload specs.
- Tightened topology-bypass consistency so repeated use of the same plane/configuration cannot report a redundant reconfiguration.

### [2026-06-06 05:58] - core_claim_plus
- Managed CPU job `f4fb2013-489` regenerated all registered baseline and SWOT artifacts in the container.
- Reproduced Fig. 5 exactly: Strawman-ICR 1500 us, SWOT 1200 us, 20.0% CCT reduction, valid schedule.
- Reproduced the same claim on two Fig. 8 scalability settings with valid schedules: 64-node AllReduce reduction 35.89% versus the paper's 39.6%, and 512-node AllReduce reduction 42.09% versus the paper's 46.9%.
- `python validate.py --compare` passed, including evaluation/method import separation and checks that evaluation reads generated artifacts.

### [2026-06-06 06:35] - core_claim_plus
- Final verification removed unscored Pairwise All-to-All target entries from the official rubric, keeping `TARGETS.md`, `EXPERIMENTS.md`, `reference.json`, and `scores.json` aligned.
- Generalized the main evaluator to discover result artifacts under `checkpoints/` instead of loading only fixed baseline/SWOT paths.
- Re-ran standalone evaluation and validation after the cleanup; both passed.

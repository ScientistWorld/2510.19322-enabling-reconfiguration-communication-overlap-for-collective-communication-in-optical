# Reproduction Milestones

**Current: core_claim**

## Progress Log

### [2026-06-06 05:45] - none
- Read the paper and identified the core method as a PuLP/CBC MILP scheduler for reconfiguration-communication overlap.
- Implemented the initial workload definitions, baseline simulator, SWOT scheduler, method-agnostic evaluator, scripts, scoring reference, and benchmark documentation.
- Preparing first CPU job to verify the method runs end-to-end inside the managed container.

### [2026-06-06 06:20] - none
- Audited the implementation and confirmed it targets the paper's MILP scheduling method rather than a surrogate.
- Fixed scoring issues so default scores match the paper-reported reference experiment and evaluation independently validates submitted schedules.
- Resubmitting a CPU smoke job because no completed `checkpoints/` artifacts were present.

### [2026-06-06 06:55] - core_claim
- Completed the managed CPU smoke job successfully.
- Ran the paper's SWOT MILP scheduler and the strawman ICR baseline on the Fig. 5 Rabenseifner AllReduce timing target.
- Reproduced the paper's core timing claim: strawman ICR CCT 1500 us, SWOT CCT 1200 us, and 20.0% CCT reduction.
- Verified `scoring/reference.json` and `scoring/scores.json` with `python validate.py --compare`; all structure, separation, and score checks passed.

## Stop Justification

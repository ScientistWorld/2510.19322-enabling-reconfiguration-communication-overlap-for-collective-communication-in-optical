# Reproduction Milestones

**Current: core_claim**

## Progress Log

### [2026-06-06 01:35] - core_claim
- Managed CPU job ran `scripts/reproduce.sh` successfully.
- Reproduced the paper's Fig. 5 Rabenseifner AllReduce example: Strawman-ICR 1500 us, SWOT 1200 us, 20% CCT reduction, valid schedule.

### [2026-06-06 05:48] - core_claim
- Added two paper Fig. 8 AllReduce scalability targets to the benchmark plan.
- Fixed evaluator artifact merging so `eval/` independently validates generated schedules from their workload specs.
- Tightened topology-bypass consistency so repeated use of the same plane/configuration cannot report a redundant reconfiguration.

# Reproduction Milestones

**Current: core_claim**

## Progress Log

### [2026-06-06 05:35] - method_runs
- Implemented the SWOT MILP scheduler with heterogeneous message splitting, asynchronous per-plane reconfiguration timelines, and topology bypassing.
- Ran the baseline, method, and evaluator end-to-end in managed job `7126c74f-64d`.

### [2026-06-06 05:40] - core_claim
- Reproduced the paper's Fig. 5 core claim: SWOT reduces CCT from 1500.0 us for Strawman-ICR to 1200.0 us.
- Independent evaluator confirmed the generated SWOT schedule is valid and preserves collective step ordering, per-plane serial resource use, and transmission-after-reconfiguration precedence.

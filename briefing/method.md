# Paper's Method

## Key Contribution

The paper proposes SWOT, an offline scheduler for collective communication over optical circuit switched networks. SWOT makes intra-collective topology reconfiguration practical by overlapping reconfiguration with data transmission.

## Approach

SWOT formulates collective execution as a mixed-integer linear program. For every collective step and optical plane, it decides the message volume assigned to that plane, whether the plane reconfigures, and the transmission and reconfiguration timing. The objective is to minimize communication completion time.

The scheduler implements three coupled mechanisms:

- Heterogeneous message splitting: unevenly divide a step's traffic across optical planes.
- Asynchronous overlapping: allow one plane to reconfigure while another plane is still transmitting.
- Topology bypassing: skip intermediate topologies on planes that are not used for those steps.

The constraints enforce traffic conservation, transmission duration under an alpha-beta model, reconfiguration duration, circuit readiness before transmission, serial resource use per OCS plane, and global step barriers required by collective algorithms.

## Reproduction (`method/swot_scheduler.py`, exposed as `scripts/solvers/swot.sh`)

- The paper's MILP (Eqs. 1-11). The `last_cfg`/`s_ij` bypass logic is linearized with pairwise "most recent previous use" implications; the paper's own `last_cfg` encoding is available (`build_model(..., formulation="paper")`), has the same optimum, and was about twice as slow per CBC node with no better incumbents in a probe, so it is not the default. A plane's first use is free (planes are pre-configured), as in the paper's Fig. 5.
- Solved with CBC via PuLP, CBC's default single-threaded search, fixed CBC seeds.
- **Budget.** The paper uses a 120 s CBC time limit. A time limit makes the schedule depend on the machine and its load, so the reproduction stops CBC after a fixed number of branch-and-bound nodes instead (`method/budget.json`): 5800 nodes for collectives of up to 14 steps, scaled by (14 / steps)^2 for longer ones (CBC's node rate fell about that fast with the number of steps). The budget was calibrated once on the compute node so that CBC uses roughly 50-110 of the 120 CPU-seconds; the schedule is then the same on any machine. The evaluator's CPU budget is only a safety stop (CBC `sec`). CBC's `timeMode cpu` is not used: a time-limited stop in that mode wrote unusable solutions.
- The paper leaves the big-M constant unspecified. The reproduction uses the lockstep (Strawman-ICR) completion time as M and bounds the CCT by it. The lockstep schedule is feasible, so the MILP optimum is unchanged (`--big-m horizon` keeps the loose variant of earlier iterations).
- The MILP's plane-use/split decisions are written with exact earliest-start timing. If CBC returns no incumbent, the lockstep schedule is written.

## Main Claims

The primary claim is that demand-aware overlapping schedules reduce CCT compared with naive intra-collective reconfiguration and static optical scheduling while preserving collective correctness. The paper reports a 20% reduction in its 8-node design-intuition example and peak reductions up to 89.7% across larger simulated collective workloads.

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

- The paper's MILP (Eqs. 1-11): the `last_cfg`/`s_ij` logic is linearized with pairwise "most recent previous use" implications. A plane's first use is free (planes are pre-configured), as in the paper's Fig. 5.
- Solved with CBC via PuLP under the paper's 120 s limit, single thread, fixed CBC seeds.
- The paper leaves the big-M constant unspecified. The reproduction uses the lockstep (Strawman-ICR) completion time as M and bounds the CCT by it. The lockstep schedule is feasible, so the MILP optimum is unchanged. Earlier iterations used a loose horizon M, which let the time-limited incumbent end up worse than lockstep on some large k=8 instances (`--big-m horizon` keeps that variant).
- The MILP's plane-use/split decisions are written with exact earliest-start timing. If CBC returns no incumbent, the lockstep schedule is written.

## Main Claims

The primary claim is that demand-aware overlapping schedules reduce CCT compared with naive intra-collective reconfiguration and static optical scheduling while preserving collective correctness. The paper reports a 20% reduction in its 8-node design-intuition example and peak reductions up to 89.7% across larger simulated collective workloads.

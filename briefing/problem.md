# Problem Definition

## Research Question

How can a scheduler minimize collective-communication completion time (CCT) in an optical circuit switched cluster when the collective algorithm requires a sequence of changing pairwise communication topologies and switching a topology takes non-negligible time?

## Setting

`p` compute nodes are connected by `k` parallel optical planes (one optical circuit switch per plane). Every node has one interface per plane; the per-node bandwidth is fixed at 800 Gbps, so each plane runs at `B = 800/k` Gbps. A collective operation (AllReduce, ReduceScatter, All-to-All, ...) implemented by a given algorithm is an ordered list of communication steps. Each step has

- a required topology (an integer ID; equal IDs within one collective mean the same pairing), and
- a per-node message volume in MB.

Steps are sequential: step `i+1` relies on data produced by step `i`.

## What a schedule decides

For every step, which planes carry part of that step's volume and how much each carries, when each plane switches topology, and when each transmission starts. The physical rules every schedule must satisfy:

1. **Traffic conservation.** The volumes carried in a step sum to the step's volume; every listed transmission carries a positive volume on a plane index in `[0, k)`.
2. **Transmission time (alpha-beta model).** A plane carrying `d` MB in a step is busy for at least `d / B + T_lat`, with `B` in MB/us (`Gbps / 8000`) and base latency `T_lat`.
3. **Circuit readiness.** A plane carries a step only if it is configured for that step's topology. Changing a plane's topology takes `T_recfg`; the plane cannot transmit while switching and only starts switching after its previous transmission ends. A plane's first use needs no switch (planes are configured before the collective starts); a later use with the same topology as that plane's previous use needs no switch.
4. **Serial use.** A plane does one thing at a time.
5. **Step barrier.** No transmission of step `i+1` starts before every transmission of step `i` has ended.

The collective starts at time 0; its CCT is the end of the last transmission.

## Workloads

Instances come from the collective algorithms and network settings of the source paper's evaluation (see `data/collectives.py` for generators): Rabenseifner ReduceScatter / AllReduce (recursive halving/doubling), Bruck All-to-All and Pairwise-exchange All-to-All, on 9-1024 nodes, with `k` in {2, 4, 8}, payloads of 1-512 MB, `T_lat` = 20 us and `T_recfg` from 20 us to 20 ms. Public train instances are in `eval/train/instances.json`; held-out test instances are drawn from the same families and ranges.

## Why It Matters

Distributed ML training spends substantial time in collective communication. Optical circuit switches provide high bandwidth, but a fixed topology cannot serve dynamic communication patterns with limited optical degree, and naively switching every plane at every step adds the switching delay to the critical path.

## Success Criteria

Valid schedules with lower CCT than the naive lockstep reconfiguration baseline (all planes serve every step with an even split and switch together whenever the topology changes), under fixed optical resources, bandwidth, latencies and collective workload, produced within a fixed per-instance compute budget.

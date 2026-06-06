# Problem Definition

## Research Question

How can a scheduler minimize collective-communication completion time in an optical circuit switched cluster when collective algorithms require a sequence of changing pairwise communication topologies?

The benchmark considers `p` compute nodes connected by `k` optical planes. A collective operation is represented as ordered communication steps. Each step has a required topology/configuration and a message volume. A valid schedule must transfer every step's full message volume while respecting optical circuit setup time, per-plane serial resource use, and the sequential barriers of the collective algorithm.

## Why It Matters

Distributed ML training spends substantial time in collective communication. Optical circuit switches can provide high bandwidth, but static topologies underuse links for dynamic communication patterns and naive per-step reconfiguration can add prohibitive switching delay.

## Success Criteria

A successful system produces valid execution schedules with lower communication completion time than static or naive dynamic baselines under fixed optical resources, bandwidth, latency, and collective workload.

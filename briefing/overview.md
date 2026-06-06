# Overview

- **Paper ID:** 2510.19322
- **Title:** Enabling Reconfiguration-Communication Overlap for Collective Communication in Optical Networks
- **Domain:** Distributed systems / optical networking / collective communication
- **TL;DR:** The paper schedules optical topology reconfiguration inside collective communication operations so switching latency is hidden behind data transmission.

## Short Summary

The paper studies collective communication in distributed ML clusters connected by optical circuit switches. Dynamic collective algorithms need changing topologies, but static optical configurations waste bandwidth and naive per-step reconfiguration pays high switching latency. SWOT addresses this with an offline MILP scheduler that jointly chooses message splits, reconfiguration timing, and topology bypasses. Simulations show lower communication completion time across several collective algorithms and network settings.

## Key Results

- In the paper's 8-node Rabenseifner AllReduce example, CCT drops from 1500 us to 1200 us.
- Across algorithm-level simulations, reported peak CCT reductions reach 89.7%.
- The method remains valid across optical degrees and reconfiguration latencies from 0.02 ms to 20 ms.

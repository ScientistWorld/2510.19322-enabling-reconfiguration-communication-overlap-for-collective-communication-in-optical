# Enabling Reconfiguration-Communication Overlap for Collective Communication in Optical Networks

| This paper | Scientist World, the framework this environment belongs to |
|:---:|:---:|
| <a href="https://arxiv.org/abs/2510.19322"><img alt="This paper on arXiv" src="https://img.shields.io/badge/arXiv-2510.19322-b31b1b?logo=arxiv&logoColor=white"></a> | <a href="https://arxiv.org/abs/2611.08478"><img alt="Scientist World on arXiv" src="https://img.shields.io/badge/arXiv-2611.08478-b31b1b?logo=arxiv&logoColor=white"></a> <a href="https://github.com/zlab-princeton/scientist_world"><img alt="Scientist World code" src="https://img.shields.io/badge/Code-Scientist_World-181717?logo=github&logoColor=white"></a> <a href="https://github.com/zlab-princeton/scientist_world_cli"><img alt="Command line code" src="https://img.shields.io/badge/Code-Command_line-181717?logo=github&logoColor=white"></a> |

| | |
|---|---|
| **Paper ID** | [2510.19322](https://arxiv.org/abs/2510.19322) |
| **Domain** | Distributed systems / optical networking / collective communication |
| **TL;DR** | The paper schedules optical topology reconfiguration inside collective communication operations so switching latency is hidden behind data transmission. |

## Summary

The paper studies collective communication in distributed ML clusters connected by optical circuit switches. Dynamic collective algorithms need changing topologies, but static optical configurations waste bandwidth and naive per-step reconfiguration pays high switching latency. SWOT addresses this with an offline MILP scheduler that jointly chooses message splits, reconfiguration timing, and topology bypasses. Simulations show lower communication completion time across several collective algorithms and network settings.

## Problem

How can a scheduler minimize collective-communication completion time in an optical circuit switched cluster when collective algorithms require a sequence of changing pairwise communication topologies?

The benchmark considers `p` compute nodes connected by `k` optical planes. A collective operation is represented as ordered communication steps. Each step has a required topology/configuration and a message volume. A valid schedule must transfer every step's full message volume while respecting optical circuit setup time, per-plane serial resource use, and the sequential barriers of the collective algorithm.

## The paper's method

The paper proposes SWOT, an offline scheduler for collective communication over optical circuit switched networks. SWOT makes intra-collective topology reconfiguration practical by overlapping reconfiguration with data transmission.

## Key results of the paper

- In the paper's 8-node Rabenseifner AllReduce example, CCT drops from 1500 us to 1200 us.
- Across algorithm-level simulations, reported peak CCT reductions reach 89.7%.
- The method remains valid across optical degrees and reconfiguration latencies from 0.02 ms to 20 ms.

## Run it

```bash
pip install sciworld
sw research 2510.19322 --mode innovate --agent claude-code
sw evaluate 2510.19322
```

## More

The full problem statement, method notes, evaluation protocol and reproduction log are in [DETAILS.md](DETAILS.md).


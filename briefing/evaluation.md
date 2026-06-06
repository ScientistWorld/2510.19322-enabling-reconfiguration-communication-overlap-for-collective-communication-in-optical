# Evaluation

## Metrics

- `cct_us`: communication completion time in microseconds. Lower is better.
- `cct_reduction_vs_strawman_pct`: percent CCT reduction relative to the naive intra-collective reconfiguration baseline. Higher is better.
- `valid_schedule`: 1 if the schedule satisfies traffic conservation, circuit readiness, per-plane serial use, and collective step barriers; 0 otherwise. Higher is better.
- `reconfiguration_events`: number of topology reconfigurations scheduled across optical planes. Lower is better when CCT is comparable.

## Baselines and Targets

The primary baseline is naive intra-collective reconfiguration: all optical planes serve each collective step in lockstep with an even message split, and the system pays one global reconfiguration delay between adjacent steps requiring different topologies.

The core target is the paper's 8-node Rabenseifner AllReduce example with two 400 Gbps optical planes, 200 us reconfiguration latency, 40 MB payload, and no base latency in the illustrated timing model. The paper reports 1500 us CCT for the naive baseline, 1200 us CCT for the optimized schedule, and 20% CCT reduction.

## Evaluation Protocol

Run `scripts/reproduce.sh` to generate baseline and scheduler artifacts under `checkpoints/`, then run `scripts/evaluate.sh` to write `scoring/scores.json`. Evaluation code reads only artifacts and code under `eval/`; it does not import the proposed method implementation.

All comparisons must use the same collective step sequence, optical degree, per-link bandwidth, base latency, and reconfiguration latency. Do not compare methods that alter the collective semantics or add optical planes/bandwidth.

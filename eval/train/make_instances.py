"""Generate the frozen public train instances (eval/train/instances.json).

    python -m eval.train.make_instances

The three scored families follow the source paper's evaluation settings
(Sections 4.2-4.3). Within each family, every instance gets an evenly
spaced quantile (so the slices have the same mix of difficulty), mapped into
the part of the family's share band that its payload range can reach; its
payload is set by bisection to hit that share. Duplicate instances are
redrawn. The share is how much of
the lockstep (Strawman-ICR) completion time is spent switching:

    switching_share = (#topology changes x T_recfg) / CCT_strawman in SHARE_BAND[family].

Outside that band the scheduling problem is degenerate: below it, lockstep is
close to optimal for every scheduler; above it, a fixed round-robin relay of
plane groups is close to optimal. (AllReduce at k=4 uses a 0.80 cap: above it,
on 18-20 step collectives, a fixed relay already matches the best schedules
found, which says nothing about scheduling skill.) Settings where a fixed
round-robin relay of plane groups (a 15-line rule) matches or beats the
paper's budget-limited MILP are not scored, because there the test would
reward a hand-written rule rather than scheduling: AllReduce, Bruck and
Pairwise All-to-All at k=8 and Bruck at k=4. These are long or
all-distinct-topology collectives on many interchangeable planes, the regime
the paper itself reports its time-limited solver handles badly (Section
4.3.1). This is a property of the
instance alone and does not depend on any scheduler. The held-out test slice
is drawn the same way with a different, private seed.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from data.collectives import make_instance

HERE = Path(__file__).resolve().parent
SLICE = "train"
PREFIX = "tr"
SEED = 20_251_022
SHARE_BAND = {"allreduce_scaling": (0.35, 0.80), "high_optical_degree": (0.35, 0.92),
              "hardware_sensitivity": (0.35, 0.92)}

# Families added in iteration 13 where the paper's own budget-limited solver
# falls short: AllReduce at optical degree 8 (Fig. 7(b) setting; Section 4.3.1
# reports that at k=8 the 120 s solver returns sub-optimal schedules for
# halving-doubling) and AllReduce beyond the paper's 1024 nodes at k=4 (the
# Fig. 8(a) scaling axis, extended). Each family is drawn from its own random
# stream, so the families above keep their instances. Payloads are stratified
# over ``draw_band``; instances whose switching share falls outside
# ``keep_band`` are dropped (an instance property, independent of any scheduler).
EXTRA_FAMILIES = {
    "allreduce_high_degree": {"algorithm": "rabenseifner_allreduce", "k": 8, "recfg": 200.0,
                              "nodes": [64, 256, 1024, 4096, 16384], "per_size": 3,
                              "payload": (1.0, 4096.0), "draw_band": (0.35, 0.85), "keep_band": (0.35, 0.85)},
    "allreduce_large_scale": {"algorithm": "rabenseifner_allreduce", "k": 4, "recfg": 200.0,
                              "nodes": [2048, 4096, 8192, 16384], "per_size": 3,
                              "payload": (1.0, 4096.0), "draw_band": (0.35, 0.80), "keep_band": (0.35, 0.80)},
    "reducescatter_large_scale": {"algorithm": "rabenseifner_reducescatter", "k": 8, "recfg": 200.0,
                                  "nodes": [2048, 4096, 8192, 16384], "per_size": 3,
                                  "payload": (1.0, 8192.0), "draw_band": (0.35, 0.92), "keep_band": (0.35, 0.92)},
}

def strawman_cct_us(spec) -> float:
    bw = spec.per_link_gbps / 8000.0
    total, previous = 0.0, None
    for step in spec.steps:
        if previous is not None and step.config != previous:
            total += spec.reconfig_latency_us
        total += step.message_mb / (spec.optical_degree * bw) + spec.base_latency_us
        previous = step.config
    return total


def switching_share(spec) -> float:
    changes = sum(1 for a, b in zip(spec.steps, spec.steps[1:]) if a.config != b.config)
    return changes * spec.reconfig_latency_us / strawman_cct_us(spec)


def payload_for_share(algorithm, nodes, k, recfg, payload_range, target):
    """Payload (3 decimals) whose switching share is closest to ``target``; share falls as payload grows."""
    lo, hi = (math.log(x) for x in payload_range)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        spec = make_instance("x", algorithm, nodes, round(math.exp(mid), 3), k, reconfig_latency_us=recfg)
        if switching_share(spec) > target:
            lo = mid
        else:
            hi = mid
    return round(math.exp(0.5 * (lo + hi)), 3)


def reachable_band(experiment, algorithm, nodes, k, recfg, payload_range):
    """The family's share band intersected with the shares the payload range can reach."""
    lo, hi = SHARE_BAND[experiment]
    at_max = switching_share(make_instance("x", algorithm, nodes, payload_range[1], k, reconfig_latency_us=recfg))
    at_min = switching_share(make_instance("x", algorithm, nodes, payload_range[0], k, reconfig_latency_us=recfg))
    return max(lo, at_max), min(hi, at_min)


def draw(rng, experiment, algorithm, nodes, k, recfg, payload_range, quantile):
    band = SHARE_BAND[experiment]
    lo, hi = reachable_band(experiment, algorithm, nodes, k, recfg, payload_range)
    target = lo + (hi - lo) * quantile if hi > lo else 0.5 * (band[0] + band[1])
    payload = payload_for_share(algorithm, nodes, k, recfg, payload_range, target)
    spec = make_instance("x", algorithm, nodes, payload, k, reconfig_latency_us=recfg)
    if band[0] <= switching_share(spec) <= band[1]:
        return payload
    lo, hi = (math.log(x) for x in payload_range)
    for _ in range(20_000):
        payload = round(math.exp(rng.uniform(lo, hi)), 3)
        spec = make_instance("x", algorithm, nodes, payload, k, reconfig_latency_us=recfg)
        if band[0] <= switching_share(spec) <= band[1]:
            return payload
    raise RuntimeError(f"no payload in band for {algorithm} {nodes} k={k} recfg={recfg}")


def plan(rng):
    """(experiment, algorithm, nodes, k, T_recfg, payload range) per instance."""
    items = []
    # Fig. 8(a): Rabenseifner AllReduce scaling, k=4 at 200 Gbps, 200 us switching.
    nodes = [64, 128, 256, 512, 1024] * 2
    rng.shuffle(nodes)
    for p in nodes:
        items.append(("allreduce_scaling", "rabenseifner_allreduce", p, 4, 200.0, (16.0, 64.0)))
    # Fig. 7(a): Rabenseifner ReduceScatter at k=8 (100 Gbps), 200 us switching,
    # 128-1024 nodes; three instances per cluster size.
    for p in [128, 256, 512, 1024] * 3:
        items.append(("high_optical_degree", "rabenseifner_reducescatter", p, 8, 200.0, (1.0, 512.0)))
    # Section 4.3: every (k, T_recfg) cell of the paper's sweep once, 256 nodes
    # (9 or 17 for Pairwise), payload around the transmission/switching knee.
    # Each (k, T_recfg) cell once: all four algorithms at k=2; at k=4 no Bruck;
    # at k=8 ReduceScatter only (see the module docstring).
    for k in (2, 4, 8):
        algos = {
            2: ["rabenseifner_reducescatter", "rabenseifner_allreduce", "bruck_alltoall", "pairwise_alltoall"],
            4: ["rabenseifner_reducescatter", "rabenseifner_allreduce", "pairwise_alltoall", "rabenseifner_allreduce"],
            8: ["rabenseifner_reducescatter"] * 4,
        }[k]
        rng.shuffle(algos)
        for r, a in zip((20.0, 200.0, 2000.0, 20000.0), algos):
            p = rng.choice([9, 17]) if a == "pairwise_alltoall" else 256
            items.append(("hardware_sensitivity", a, p, k, r, (0.25, 8192.0)))
    return items


def stratified_quantiles(rng, items):
    """Evenly spaced quantiles (one per instance, jittered, randomly assigned) within each family."""
    quantiles = []
    for experiment in dict.fromkeys(item[0] for item in items):
        idx = [i for i, item in enumerate(items) if item[0] == experiment]
        values = [(j + rng.random()) / len(idx) for j in range(len(idx))]
        rng.shuffle(values)
        quantiles.extend(zip(idx, values))
    return dict(quantiles)


def build_extra(family: str, cfg: dict, start: int, used: set) -> list:
    """Instances of one iteration-13 family (own random stream, stratified over draw_band)."""
    rng = random.Random(f"{SEED}:{family}")
    sizes = list(cfg["nodes"]) * cfg["per_size"]
    rng.shuffle(sizes)
    quantiles = [(j + rng.random()) / len(sizes) for j in range(len(sizes))]
    rng.shuffle(quantiles)
    lo_band, hi_band = cfg["draw_band"]
    out = []
    for n, (nodes, quantile) in enumerate(zip(sizes, quantiles), start=start):
        alg, k, recfg, prange = cfg["algorithm"], cfg["k"], cfg["recfg"], cfg["payload"]
        at_max = switching_share(make_instance("x", alg, nodes, prange[1], k, reconfig_latency_us=recfg))
        at_min = switching_share(make_instance("x", alg, nodes, prange[0], k, reconfig_latency_us=recfg))
        lo, hi = max(lo_band, at_max), min(hi_band, at_min)
        payload = payload_for_share(alg, nodes, k, recfg, prange, lo + (hi - lo) * quantile)
        while (alg, nodes, k, recfg, payload) in used:  # no duplicate instances
            quantile = min(0.999, max(0.001, quantile + rng.uniform(-0.05, 0.05)))
            payload = payload_for_share(alg, nodes, k, recfg, prange, lo + (hi - lo) * quantile)
        used.add((alg, nodes, k, recfg, payload))
        iid = f"{PREFIX}{n:02d}"
        spec = make_instance(iid, alg, nodes, payload, k, reconfig_latency_us=recfg)
        keep_lo, keep_hi = cfg["keep_band"]
        if not keep_lo <= switching_share(spec) <= keep_hi:
            continue
        payload_json = spec.to_json()
        payload_json.update({"id": iid, "experiment": family, "description": ""})
        out.append(payload_json)
    return out


def build() -> dict:
    rng = random.Random(SEED)
    experiments: dict[str, list] = {}
    items = plan(rng)
    quantiles = stratified_quantiles(rng, items)
    used = set()
    for n, (experiment, algorithm, nodes, k, recfg, prange) in enumerate(items, start=1):
        quantile = quantiles[n - 1]
        payload = draw(rng, experiment, algorithm, nodes, k, recfg, prange, quantile)
        while (algorithm, nodes, k, recfg, payload) in used:  # no duplicate instances
            quantile = min(0.999, max(0.001, quantile + rng.uniform(-0.05, 0.05)))
            payload = draw(rng, experiment, algorithm, nodes, k, recfg, prange, quantile)
        used.add((algorithm, nodes, k, recfg, payload))
        iid = f"{PREFIX}{n:02d}"
        spec = make_instance(iid, algorithm, nodes, payload, k, reconfig_latency_us=recfg)
        payload_json = spec.to_json()
        payload_json.update({"id": iid, "experiment": experiment, "description": ""})
        experiments.setdefault(experiment, []).append(payload_json)
    start = len(items) + 1
    for family, cfg in EXTRA_FAMILIES.items():
        drawn = build_extra(family, cfg, start, used)
        start += len(cfg["nodes"]) * cfg["per_size"]
        if drawn:
            experiments[family] = drawn
    return {"slice": SLICE, "generator": f"eval/{SLICE}/make_instances.py", "experiments": experiments}


def main() -> None:
    suite = build()
    (HERE / "instances.json").write_text(json.dumps(suite, indent=1))
    for experiment, items in suite["experiments"].items():
        for item in items:
            print(experiment, item["id"], item["algorithm"], item["nodes"], item["payload_mb"],
                  f"k={item['optical_degree']}", f"recfg={item['reconfig_latency_us']:g}",
                  f"steps={len(item['steps'])}")


if __name__ == "__main__":
    main()

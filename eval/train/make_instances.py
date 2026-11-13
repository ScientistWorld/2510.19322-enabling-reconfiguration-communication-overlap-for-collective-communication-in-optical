"""Generate the frozen public train instances (eval/train/instances.json).

    python -m eval.train.make_instances

The three scored families follow the source paper's evaluation settings
(Sections 4.2-4.3). Within each family, every instance gets a target
switching share at evenly spaced quantiles of the family's band (so the
slices have the same mix of difficulty), and its payload is set by bisection
to reach it within the family's payload range (falling back to log-uniform
rejection sampling when the range cannot reach it). The share is how much of
the lockstep (Strawman-ICR) completion time is spent switching:

    switching_share = (#topology changes x T_recfg) / CCT_strawman in SHARE_BAND[family].

Outside that band the scheduling problem is degenerate: below it, lockstep is
close to optimal for every scheduler; above it, a fixed round-robin relay of
plane groups is close to optimal. (AllReduce at k=4 uses a 0.80 cap: above it,
on 18-20 step collectives, a fixed relay already matches the best schedules
found, which says nothing about scheduling skill.) Bruck and Pairwise
All-to-All at k=8 are not scored: every step needs a different topology on
eight interchangeable planes, the regime the paper reports its time-limited
solver handles badly (Section 4.3.1), and a fixed relay rule beats the
paper's MILP there. This is a property of the
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


def draw(rng, experiment, algorithm, nodes, k, recfg, payload_range, target):
    band = SHARE_BAND[experiment]
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
    # Fig. 7(a)-(b): Rabenseifner ReduceScatter and AllReduce at k=8 (100 Gbps),
    # 200 us switching, 128-1024 nodes; six instances each.
    for a in ["rabenseifner_reducescatter", "rabenseifner_allreduce"]:
        sizes = [128, 256, 512, 1024] + rng.sample([128, 256, 512, 1024], 2)
        for p in sorted(sizes):
            items.append(("high_optical_degree", a, p, 8, 200.0, (1.0, 512.0)))
    # Section 4.3: every (k, T_recfg) cell of the paper's sweep once, 256 nodes
    # (9 or 17 for Pairwise), payload around the transmission/switching knee.
    # Every algorithm once per optical degree at k=2 and k=4 (Rabenseifner only
    # at k=8, see above), each at a different switching latency.
    for k in (2, 4, 8):
        if k == 8:
            algos = ["rabenseifner_reducescatter", "rabenseifner_allreduce"] * 2
        else:
            algos = ["rabenseifner_reducescatter", "rabenseifner_allreduce", "bruck_alltoall", "pairwise_alltoall"]
        rng.shuffle(algos)
        for r, a in zip((20.0, 200.0, 2000.0, 20000.0), algos):
            p = rng.choice([9, 17]) if a == "pairwise_alltoall" else 256
            items.append(("hardware_sensitivity", a, p, k, r, (0.25, 8192.0)))
    return items


def stratified_targets(rng, items):
    """Target switching shares at evenly spaced quantiles of each family's band, randomly assigned."""
    targets = []
    for experiment in dict.fromkeys(item[0] for item in items):
        idx = [i for i, item in enumerate(items) if item[0] == experiment]
        lo, hi = SHARE_BAND[experiment]
        values = [lo + (hi - lo) * (j + rng.random()) / len(idx) for j in range(len(idx))]
        rng.shuffle(values)
        targets.extend(zip(idx, values))
    return dict(targets)


def build() -> dict:
    rng = random.Random(SEED)
    experiments: dict[str, list] = {}
    items = plan(rng)
    targets = stratified_targets(rng, items)
    for n, (experiment, algorithm, nodes, k, recfg, prange) in enumerate(items, start=1):
        payload = draw(rng, experiment, algorithm, nodes, k, recfg, prange, targets[n - 1])
        iid = f"{PREFIX}{n:02d}"
        spec = make_instance(iid, algorithm, nodes, payload, k, reconfig_latency_us=recfg)
        payload_json = spec.to_json()
        payload_json.update({"id": iid, "experiment": experiment, "description": ""})
        experiments.setdefault(experiment, []).append(payload_json)
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

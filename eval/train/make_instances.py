"""Generate the frozen public train instances (eval/train/instances.json).

    python -m eval.train.make_instances

The three scored families follow the source paper's evaluation settings
(Sections 4.2-4.3). Within each family, an instance's payload is drawn
log-uniformly and kept only if switching is a material but not total share of
the lockstep (Strawman-ICR) completion time:

    switching_share = (#topology changes x T_recfg) / CCT_strawman in [0.35, 0.92].

Outside that band the scheduling problem is degenerate: below it, lockstep is
close to optimal for every scheduler; above it, every scheduler that hides
switching reaches the same near-total reduction. This is a property of the
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
SHARE_BAND = (0.35, 0.92)

BIG = ("rabenseifner_reducescatter", "rabenseifner_allreduce", "bruck_alltoall")


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


def draw(rng, algorithm, nodes, k, recfg, payload_range):
    lo, hi = (math.log(x) for x in payload_range)
    for _ in range(20_000):
        payload = round(math.exp(rng.uniform(lo, hi)), 3)
        spec = make_instance("x", algorithm, nodes, payload, k, reconfig_latency_us=recfg)
        if SHARE_BAND[0] <= switching_share(spec) <= SHARE_BAND[1]:
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
    # Fig. 7: four algorithms at k=8 (100 Gbps), 200 us switching.
    # Each algorithm three times, once per cluster size (three Pairwise sizes).
    for a in ["rabenseifner_reducescatter", "rabenseifner_allreduce", "bruck_alltoall", "pairwise_alltoall"]:
        sizes = sorted(rng.sample([9, 10, 11, 12], 3)) if a == "pairwise_alltoall" else [128, 256, 512]
        for p in sizes:
            items.append(("collective_algorithms", a, p, 8, 200.0, (1.0, 512.0)))
    # Section 4.3: every (k, T_recfg) cell of the paper's sweep once, 256 nodes
    # (9 or 17 for Pairwise), payload around the transmission/switching knee.
    # Every algorithm once per optical degree, at a random switching latency.
    for k in (2, 4, 8):
        algos = ["rabenseifner_reducescatter", "rabenseifner_allreduce", "bruck_alltoall", "pairwise_alltoall"]
        rng.shuffle(algos)
        for r, a in zip((20.0, 200.0, 2000.0, 20000.0), algos):
            p = rng.choice([9, 17]) if a == "pairwise_alltoall" else 256
            items.append(("hardware_sensitivity", a, p, k, r, (0.25, 8192.0)))
    return items


def build() -> dict:
    rng = random.Random(SEED)
    experiments: dict[str, list] = {}
    for n, (experiment, algorithm, nodes, k, recfg, prange) in enumerate(plan(rng), start=1):
        payload = draw(rng, algorithm, nodes, k, recfg, prange)
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

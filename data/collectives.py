"""Collective communication workloads for the optical-scheduling benchmark.

The functions in this module are method-agnostic: they define communication
steps and timing parameters that any scheduler can consume.

A workload instance is serialized as JSON with the fields of ``ExperimentSpec``
(see ``ExperimentSpec.to_json``). This is the format a solver receives from the
evaluators through ``scripts/solvers/<method>.sh``.

Timing model (alpha-beta, per optical plane):
  * a plane carrying ``d`` MB in a step is busy for ``d / B + base_latency_us``
    where ``B = per_link_gbps / 8000`` MB/us;
  * switching a plane to a different topology takes ``reconfig_latency_us``
    and the plane cannot transmit while switching;
  * every plane may be pre-configured to any topology before the collective
    starts, so a plane's first use never needs a reconfiguration;
  * step ``i+1`` cannot start on any plane before every transmission of step
    ``i`` has finished.

The scored evaluators hold their own frozen copies of their instances; this
module only describes the instance families so methods can be developed.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, List


@dataclass(frozen=True)
class CollectiveStep:
    step: int
    config: int
    message_mb: float


@dataclass(frozen=True)
class ExperimentSpec:
    name: str
    description: str
    nodes: int
    optical_degree: int
    per_link_gbps: float
    base_latency_us: float
    reconfig_latency_us: float
    steps: List[CollectiveStep]
    algorithm: str = "custom"
    payload_mb: float = 0.0

    def to_json(self) -> Dict:
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def spec_from_json(payload: Dict) -> ExperimentSpec:
    """Build an ``ExperimentSpec`` from an instance JSON object."""
    return ExperimentSpec(
        name=str(payload.get("name", payload.get("id", "instance"))),
        description=str(payload.get("description", "")),
        nodes=int(payload.get("nodes", 0)),
        optical_degree=int(payload["optical_degree"]),
        per_link_gbps=float(payload["per_link_gbps"]),
        base_latency_us=float(payload.get("base_latency_us", 0.0)),
        reconfig_latency_us=float(payload["reconfig_latency_us"]),
        steps=[
            CollectiveStep(int(s["step"]), int(s["config"]), float(s["message_mb"]))
            for s in payload["steps"]
        ],
        algorithm=str(payload.get("algorithm", "custom")),
        payload_mb=float(payload.get("payload_mb", 0.0)),
    )


def load_instance(path: str | Path) -> ExperimentSpec:
    return spec_from_json(json.loads(Path(path).read_text()))


def mb_per_us(gbps: float) -> float:
    """Convert line rate in Gbps to decimal MB/us."""
    return gbps / 8_000.0


# ---------------------------------------------------------------------------
# Collective algorithms as ordered (topology, per-node volume) steps.
# Topology IDs are local to one collective; equal IDs mean the same pairing.
# ---------------------------------------------------------------------------


def _log2_exact(nodes: int) -> int:
    if nodes <= 1 or nodes & (nodes - 1):
        raise ValueError("nodes must be a power of two")
    return nodes.bit_length() - 1


def rabenseifner_reducescatter_steps(nodes: int, payload_mb: float) -> List[CollectiveStep]:
    """Recursive halving: step s pairs i with i xor 2^(s-1) and sends M/2^s."""
    levels = _log2_exact(nodes)
    return [CollectiveStep(s, s, payload_mb / (2**s)) for s in range(1, levels + 1)]


def rabenseifner_allreduce_steps(nodes: int, payload_mb: float) -> List[CollectiveStep]:
    """Recursive-halving reduce-scatter followed by recursive-doubling allgather."""
    levels = _log2_exact(nodes)
    steps: List[CollectiveStep] = []
    step_id = 1
    for level in range(1, levels + 1):
        steps.append(CollectiveStep(step_id, level, payload_mb / (2**level)))
        step_id += 1
    for level in range(levels, 0, -1):
        steps.append(CollectiveStep(step_id, level, payload_mb / (2**level)))
        step_id += 1
    return steps


def bruck_alltoall_steps(nodes: int, payload_mb: float) -> List[CollectiveStep]:
    """Bruck all-to-all: step s sends to i+2^(s-1) every block whose index has bit s-1 set."""
    if nodes < 2:
        raise ValueError("nodes must be >= 2")
    block = payload_mb / nodes
    steps: List[CollectiveStep] = []
    s = 0
    while (1 << s) < nodes:
        count = sum(1 for j in range(nodes) if (j >> s) & 1)
        steps.append(CollectiveStep(s + 1, s + 1, count * block))
        s += 1
    return steps


def pairwise_alltoall_steps(nodes: int, payload_mb: float) -> List[CollectiveStep]:
    """Pairwise exchange: step t sends one M/p block to node i+t (mod p)."""
    if nodes < 2:
        raise ValueError("nodes must be >= 2")
    return [CollectiveStep(t, t, payload_mb / nodes) for t in range(1, nodes)]


ALGORITHMS: Dict[str, Callable[[int, float], List[CollectiveStep]]] = {
    "rabenseifner_reducescatter": rabenseifner_reducescatter_steps,
    "rabenseifner_allreduce": rabenseifner_allreduce_steps,
    "bruck_alltoall": bruck_alltoall_steps,
    "pairwise_alltoall": pairwise_alltoall_steps,
}


def make_instance(
    name: str,
    algorithm: str,
    nodes: int,
    payload_mb: float,
    optical_degree: int,
    reconfig_latency_us: float = 200.0,
    base_latency_us: float = 20.0,
    total_node_gbps: float = 800.0,
    description: str = "",
) -> ExperimentSpec:
    """One workload instance; per-link bandwidth is ``total_node_gbps / k`` as in the paper."""
    steps = ALGORITHMS[algorithm](nodes, payload_mb)
    return ExperimentSpec(
        name=name,
        description=description or f"{algorithm} on {nodes} nodes, {payload_mb:g} MB, k={optical_degree}",
        nodes=nodes,
        optical_degree=optical_degree,
        per_link_gbps=total_node_gbps / optical_degree,
        base_latency_us=base_latency_us,
        reconfig_latency_us=reconfig_latency_us,
        steps=steps,
        algorithm=algorithm,
        payload_mb=payload_mb,
    )


# ---------------------------------------------------------------------------
# The paper's own named settings (public; reproduced in scoring/scores.json).
# ---------------------------------------------------------------------------


def rabenseifner_allreduce_8node_example() -> ExperimentSpec:
    """Paper Fig. 5 8-node Rabenseifner AllReduce example.

    The paper uses a 40 MB payload. Per-step exchanged volumes are
    20, 10, 5 MB for reduce-scatter and 5, 10, 20 MB for allgather,
    with required configurations P1, P2, P3, P3, P2, P1, two 400 Gbps
    planes, 200 us switching and no base latency.
    """
    return ExperimentSpec(
        name="paper_fig5_rabenseifner_allreduce_8node",
        description="8-node Rabenseifner AllReduce timeline from the paper's design-intuition example.",
        nodes=8,
        optical_degree=2,
        per_link_gbps=400.0,
        base_latency_us=0.0,
        reconfig_latency_us=200.0,
        steps=[
            CollectiveStep(1, 1, 20.0),
            CollectiveStep(2, 2, 10.0),
            CollectiveStep(3, 3, 5.0),
            CollectiveStep(4, 3, 5.0),
            CollectiveStep(5, 2, 10.0),
            CollectiveStep(6, 1, 20.0),
        ],
        algorithm="rabenseifner_allreduce",
        payload_mb=40.0,
    )


def scaled_rabenseifner_allreduce(
    nodes: int = 16,
    optical_degree: int = 4,
    payload_mb: float = 32.0,
    total_node_gbps: float = 800.0,
    base_latency_us: float = 20.0,
    reconfig_latency_us: float = 200.0,
    name: str | None = None,
    description: str | None = None,
) -> ExperimentSpec:
    """Rabenseifner AllReduce at the paper's Fig. 8 network settings."""
    return make_instance(
        name=name or f"rabenseifner_allreduce_{nodes}node_k{optical_degree}",
        algorithm="rabenseifner_allreduce",
        nodes=nodes,
        payload_mb=payload_mb,
        optical_degree=optical_degree,
        reconfig_latency_us=reconfig_latency_us,
        base_latency_us=base_latency_us,
        total_node_gbps=total_node_gbps,
        description=description or "",
    )


PAPER_INSTANCES = {
    "paper_fig5_rabenseifner_allreduce_8node": rabenseifner_allreduce_8node_example,
    "paper_fig8_rabenseifner_allreduce_64node_k4": lambda: scaled_rabenseifner_allreduce(
        64,
        4,
        name="paper_fig8_rabenseifner_allreduce_64node_k4",
        description="Paper Fig. 8 Rabenseifner AllReduce scalability point at 64 nodes.",
    ),
    "paper_fig8_rabenseifner_allreduce_512node_k4": lambda: scaled_rabenseifner_allreduce(
        512,
        4,
        name="paper_fig8_rabenseifner_allreduce_512node_k4",
        description="Paper Fig. 8 Rabenseifner AllReduce scalability point at 512 nodes.",
    ),
}

# Backwards-compatible alias used by the batch scripts.
EXPERIMENTS = PAPER_INSTANCES


# ---------------------------------------------------------------------------
# Instance families used by the scored experiments. The evaluators hold frozen
# instances drawn from these settings. Within a family, each instance's payload
# is chosen so that the share of the lockstep (Strawman-ICR) completion time
# spent switching, (#topology changes x T_recfg) / CCT_lockstep, lies in
# ``switching_share``; the slices are stratified over that band.
# ---------------------------------------------------------------------------

FAMILIES = {
    "allreduce_scaling": {
        "paper_section": "4.2.2 / Fig. 8(a)",
        "algorithms": ["rabenseifner_allreduce"],
        "nodes": [64, 128, 256, 512, 1024],
        "payload_mb": [16.0, 64.0],
        "optical_degree": [4],
        "reconfig_latency_us": [200.0],
        "base_latency_us": 20.0,
        "switching_share": [0.35, 0.80],
    },
    "high_optical_degree": {
        "paper_section": "4.2.1 / Fig. 7(a)-(b)",
        "algorithms": ["rabenseifner_reducescatter", "rabenseifner_allreduce"],
        "nodes": [128, 256, 512, 1024],
        "payload_mb": [1.0, 512.0],
        "optical_degree": [8],
        "reconfig_latency_us": [200.0],
        "base_latency_us": 20.0,
        "switching_share": [0.35, 0.92],
    },
    "hardware_sensitivity": {
        "paper_section": "4.3 / Figs. 10-11",
        "algorithms": {
            "2": ["rabenseifner_reducescatter", "rabenseifner_allreduce", "bruck_alltoall", "pairwise_alltoall"],
            "4": ["rabenseifner_reducescatter", "rabenseifner_allreduce", "bruck_alltoall", "pairwise_alltoall"],
            "8": ["rabenseifner_reducescatter", "rabenseifner_allreduce"],
        },
        "nodes": {"default": [256], "pairwise_alltoall": [9, 17]},
        "payload_mb": [0.25, 8192.0],
        "optical_degree": [2, 4, 8],
        "reconfig_latency_us": [20.0, 200.0, 2000.0, 20000.0],
        "base_latency_us": 20.0,
        "switching_share": [0.35, 0.92],
    },
}


def switching_share(spec: ExperimentSpec) -> float:
    """Share of the lockstep (Strawman-ICR) completion time spent switching topology."""
    bw = mb_per_us(spec.per_link_gbps)
    total, changes, previous = 0.0, 0, None
    for step in spec.steps:
        if previous is not None and step.config != previous:
            total += spec.reconfig_latency_us
            changes += 1
        total += step.message_mb / (spec.optical_degree * bw) + spec.base_latency_us
        previous = step.config
    return changes * spec.reconfig_latency_us / total


def get_experiment(name: str) -> ExperimentSpec:
    try:
        return PAPER_INSTANCES[name]()
    except KeyError as exc:
        raise KeyError(f"unknown instance {name!r}; choices: {sorted(PAPER_INSTANCES)}") from exc

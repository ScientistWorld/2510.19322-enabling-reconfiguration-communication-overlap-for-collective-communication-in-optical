"""Collective communication workloads for the SWOT reproduction.

The functions in this module are method-agnostic: they define communication
steps and timing parameters that any scheduler can consume.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List


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

    def to_json(self) -> Dict:
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def mb_per_us(gbps: float) -> float:
    """Convert line rate in Gbps to decimal MB/us."""
    return gbps / 8_000.0


def rabenseifner_allreduce_8node_example() -> ExperimentSpec:
    """Paper Fig. 5 8-node Rabenseifner AllReduce example.

    The paper uses a 40 MB payload. Per-step exchanged volumes are
    20, 10, 5 MB for reduce-scatter and 5, 10, 20 MB for allgather,
    with required configurations P1, P2, P3, P3, P2, P1.
    """
    return ExperimentSpec(
        name="fig5_rabenseifner_allreduce_8node",
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
    )


def scaled_rabenseifner_allreduce(
    nodes: int = 16,
    optical_degree: int = 4,
    payload_mb: float = 32.0,
    total_node_gbps: float = 800.0,
    base_latency_us: float = 20.0,
    reconfig_latency_us: float = 200.0,
) -> ExperimentSpec:
    """A small scalable Rabenseifner AllReduce instance.

    This keeps the paper's collective-step structure while using a smaller
    instance than the 256+ node plots so the MILP solves quickly in a smoke job.
    """
    if nodes <= 1 or nodes & (nodes - 1):
        raise ValueError("nodes must be a power of two")
    levels = nodes.bit_length() - 1
    steps: List[CollectiveStep] = []
    step_id = 1
    for level in range(levels):
        steps.append(CollectiveStep(step_id, level + 1, payload_mb / (2 ** (level + 1))))
        step_id += 1
    for level in reversed(range(levels)):
        steps.append(CollectiveStep(step_id, level + 1, payload_mb / (2 ** (level + 1))))
        step_id += 1
    return ExperimentSpec(
        name=f"scaled_rabenseifner_allreduce_{nodes}node_k{optical_degree}",
        description="Scaled Rabenseifner AllReduce setting for reproducible smoke evaluation.",
        nodes=nodes,
        optical_degree=optical_degree,
        per_link_gbps=total_node_gbps / optical_degree,
        base_latency_us=base_latency_us,
        reconfig_latency_us=reconfig_latency_us,
        steps=steps,
    )


EXPERIMENTS = {
    "fig5_rabenseifner_allreduce_8node": rabenseifner_allreduce_8node_example,
    "scaled_rabenseifner_allreduce_16node_k4": lambda: scaled_rabenseifner_allreduce(16, 4),
}


def get_experiment(name: str) -> ExperimentSpec:
    try:
        return EXPERIMENTS[name]()
    except KeyError as exc:
        raise KeyError(f"unknown experiment {name!r}; choices: {sorted(EXPERIMENTS)}") from exc

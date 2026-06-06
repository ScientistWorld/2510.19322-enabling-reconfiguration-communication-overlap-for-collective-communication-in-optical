"""Paper baseline simulators for optical collective communication."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data.collectives import EXPERIMENTS, ExperimentSpec, mb_per_us


def strawman_icr(spec: ExperimentSpec) -> dict:
    """Naive intra-collective reconfiguration with lockstep planes.

    Every step uses all OCS planes with an even split. A global reconfiguration
    delay is paid between adjacent steps whose required topology differs.
    """
    bandwidth = mb_per_us(spec.per_link_gbps)
    transmit_us = 0.0
    for step in spec.steps:
        transmit_us += step.message_mb / (spec.optical_degree * bandwidth)
        if step.message_mb > 0:
            transmit_us += spec.base_latency_us
    reconfig_count = sum(
        1
        for prev, cur in zip(spec.steps, spec.steps[1:])
        if prev.config != cur.config
    )
    reconfig_us = reconfig_count * spec.reconfig_latency_us
    cct_us = transmit_us + reconfig_us
    return {
        "method": "strawman_icr",
        "experiment": spec.name,
        "cct_us": cct_us,
        "transmission_us": transmit_us,
        "reconfiguration_us": reconfig_us,
        "reconfiguration_events": reconfig_count,
        "valid_schedule": 1.0,
    }


def run(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {"experiments": {}}
    for name, factory in EXPERIMENTS.items():
        spec = factory()
        payload["experiments"][name] = {
            "spec": spec.to_json(),
            "results": {"strawman_icr": strawman_icr(spec)},
        }
    (output_dir / "baseline_results.json").write_text(json.dumps(payload, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="checkpoints/baseline")
    args = parser.parse_args()
    run(Path(args.output_dir))


if __name__ == "__main__":
    main()

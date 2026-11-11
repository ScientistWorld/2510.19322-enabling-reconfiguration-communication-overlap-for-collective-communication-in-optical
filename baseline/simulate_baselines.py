"""Paper baseline: Strawman-ICR (naive lockstep intra-collective reconfiguration).

Every step uses all OCS planes with an even split; all planes switch together
whenever the next step needs a different topology. The evaluators compute
this baseline themselves from each frozen instance; this module writes the
explicit schedules for the paper's named instances for inspection, and can
also act as a solver (``--instance/--output``) to show the lockstep schedule
passes the evaluators' validation with zero reduction.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data.collectives import EXPERIMENTS, ExperimentSpec, load_instance, mb_per_us


def strawman_schedule(spec: ExperimentSpec) -> list[dict]:
    bandwidth = mb_per_us(spec.per_link_gbps)
    k = spec.optical_degree
    schedule = []
    end = 0.0
    previous = None
    for step in spec.steps:
        switch = previous is not None and previous != step.config
        r_start = end
        r_end = r_start + (spec.reconfig_latency_us if switch else 0.0)
        t_end = r_end + step.message_mb / (k * bandwidth) + spec.base_latency_us
        for plane in range(k):
            schedule.append(
                {
                    "step": step.step,
                    "config": step.config,
                    "plane": plane,
                    "message_mb": step.message_mb / k,
                    "reconfigured": int(switch),
                    "reconfig_start_us": r_start,
                    "reconfig_end_us": r_end,
                    "transmit_start_us": r_end,
                    "transmit_end_us": t_end,
                }
            )
        end = t_end
        previous = step.config
    return schedule


def strawman_icr(spec: ExperimentSpec) -> dict:
    schedule = strawman_schedule(spec)
    events = sum(1 for prev, cur in zip(spec.steps, spec.steps[1:]) if prev.config != cur.config)
    return {
        "method": "strawman_icr",
        "experiment": spec.name,
        "cct_us": max(item["transmit_end_us"] for item in schedule),
        "reconfiguration_events": events,
        "schedule": schedule,
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
    parser.add_argument("--instance")
    parser.add_argument("--output")
    args, _ = parser.parse_known_args()
    if args.instance:
        Path(args.output).write_text(json.dumps(strawman_icr(load_instance(args.instance))))
    else:
        run(Path(args.output_dir))


if __name__ == "__main__":
    main()

"""SWOT MILP scheduler reproduction.

This implements the paper's core computation: a mixed-integer linear program
that jointly chooses heterogeneous message splits, per-plane asynchronous
reconfiguration times, and topology bypassing to minimize CCT.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict

import pulp

from data.collectives import EXPERIMENTS, ExperimentSpec, mb_per_us


def solve_swot(spec: ExperimentSpec, time_limit_s: int = 120) -> Dict:
    steps = spec.steps
    n_steps = len(steps)
    k = spec.optical_degree
    planes = range(k)
    idxs = range(n_steps)
    bandwidth = mb_per_us(spec.per_link_gbps)
    horizon = (
        sum(step.message_mb / bandwidth + spec.base_latency_us for step in steps)
        + n_steps * spec.reconfig_latency_us
        + 1_000.0
    )

    model = pulp.LpProblem(f"SWOT_{spec.name}", pulp.LpMinimize)
    use = pulp.LpVariable.dicts("u", (idxs, planes), 0, 1, cat="Binary")
    reconfig = pulp.LpVariable.dicts("r", (idxs, planes), 0, 1, cat="Binary")
    data = pulp.LpVariable.dicts("d", (idxs, planes), 0, None, cat="Continuous")
    t_start = pulp.LpVariable.dicts("t_start", (idxs, planes), 0, None)
    t_end = pulp.LpVariable.dicts("t_end", (idxs, planes), 0, None)
    r_start = pulp.LpVariable.dicts("r_start", (idxs, planes), 0, None)
    r_end = pulp.LpVariable.dicts("r_end", (idxs, planes), 0, None)
    prev_free = pulp.LpVariable.dicts("prev_free", (idxs, planes), 0, None)
    step_end = pulp.LpVariable.dicts("step_end", idxs, 0, None)
    cct = pulp.LpVariable("cct", 0, None)

    model += cct

    for i in idxs:
        step = steps[i]
        model += pulp.lpSum(data[i][j] for j in planes) == step.message_mb
        for j in planes:
            model += data[i][j] <= step.message_mb * use[i][j]
            model += data[i][j] >= 1e-6 * use[i][j]
            model += reconfig[i][j] <= use[i][j]
            model += t_end[i][j] - t_start[i][j] == data[i][j] / bandwidth + spec.base_latency_us * use[i][j]
            model += r_end[i][j] - r_start[i][j] == spec.reconfig_latency_us * reconfig[i][j]
            model += r_start[i][j] >= prev_free[i][j]
            model += t_start[i][j] >= r_end[i][j]
            if i > 0:
                model += t_start[i][j] >= step_end[i - 1]
            model += step_end[i] >= t_end[i][j] - horizon * (1 - use[i][j])

            if i == 0:
                model += prev_free[i][j] == 0
                model += reconfig[i][j] == 0
            else:
                model += prev_free[i][j] >= prev_free[i - 1][j]
                model += prev_free[i][j] >= t_end[i - 1][j] - horizon * (1 - use[i - 1][j])
                model += prev_free[i][j] >= r_end[i - 1][j] - horizon * (1 - reconfig[i - 1][j])

                # If the most recent previous step that used this OCS had a
                # different topology, this step must reconfigure. If an
                # intervening use exists, the constraint is relaxed, allowing
                # topology bypassing to be represented by skipped uses.
                for prev in range(i):
                    if steps[prev].config == step.config:
                        continue
                    intervening = pulp.lpSum(use[h][j] for h in range(prev + 1, i))
                    model += reconfig[i][j] >= use[i][j] + use[prev][j] - intervening - 1

        if i > 0:
            model += step_end[i] >= step_end[i - 1]
    model += cct >= step_end[n_steps - 1]

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit_s)
    status_code = model.solve(solver)
    status = pulp.LpStatus[status_code]
    if status not in {"Optimal", "Not Solved", "Integer Feasible"}:
        raise RuntimeError(f"MILP failed for {spec.name}: {status}")

    schedule = []
    for i, step in enumerate(steps):
        for j in planes:
            if pulp.value(use[i][j]) and pulp.value(use[i][j]) > 0.5:
                schedule.append(
                    {
                        "step": step.step,
                        "config": step.config,
                        "plane": j,
                        "message_mb": float(pulp.value(data[i][j])),
                        "reconfigured": int(round(pulp.value(reconfig[i][j]))),
                        "reconfig_start_us": float(pulp.value(r_start[i][j])),
                        "reconfig_end_us": float(pulp.value(r_end[i][j])),
                        "transmit_start_us": float(pulp.value(t_start[i][j])),
                        "transmit_end_us": float(pulp.value(t_end[i][j])),
                    }
                )

    reconfig_events = sum(item["reconfigured"] for item in schedule)
    return {
        "method": "swot",
        "experiment": spec.name,
        "solver_status": status,
        "cct_us": float(pulp.value(cct)),
        "reconfiguration_events": int(reconfig_events),
        "reconfiguration_us": float(reconfig_events * spec.reconfig_latency_us),
        "valid_schedule": 1.0 if _validate_schedule(spec, schedule) else 0.0,
        "schedule": schedule,
    }


def _validate_schedule(spec: ExperimentSpec, schedule: list[dict]) -> bool:
    by_step: Dict[int, list[dict]] = {}
    for item in schedule:
        by_step.setdefault(item["step"], []).append(item)
        if item["transmit_start_us"] + 1e-6 < item["reconfig_end_us"]:
            return False
    previous_end = 0.0
    for step in spec.steps:
        items = by_step.get(step.step, [])
        if not items:
            return False
        if abs(sum(item["message_mb"] for item in items) - step.message_mb) > 1e-4:
            return False
        if any(item["config"] != step.config for item in items):
            return False
        if any(item["transmit_start_us"] + 1e-6 < previous_end for item in items):
            return False
        previous_end = max(item["transmit_end_us"] for item in items)
    return True


def run(output_dir: Path, time_limit_s: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {"experiments": {}}
    for name, factory in EXPERIMENTS.items():
        spec = factory()
        payload["experiments"][name] = {
            "spec": spec.to_json(),
            "results": {"swot": solve_swot(spec, time_limit_s=time_limit_s)},
        }
    (output_dir / "swot_results.json").write_text(json.dumps(payload, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="checkpoints/swot")
    parser.add_argument("--time-limit-s", type=int, default=120)
    args = parser.parse_args()
    run(Path(args.output_dir), args.time_limit_s)


if __name__ == "__main__":
    main()

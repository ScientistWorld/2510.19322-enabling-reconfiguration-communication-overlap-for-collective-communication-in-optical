"""SWOT MILP scheduler reproduction.

This implements the paper's core computation (Section 3.2): a mixed-integer
linear program that jointly chooses heterogeneous message splits (d_ij),
per-plane asynchronous reconfiguration times, and topology bypassing (r_ij,
u_ij) to minimize the collective completion time, solved with CBC via PuLP
under the paper's 120 s time limit.

Solver interface (used by every evaluator through scripts/solvers/swot.sh):

    python -m method.swot_scheduler --instance IN.json --output OUT.json --time-limit-s 120

The MILP's discrete decisions (which planes carry which volume in each step)
are serialized with exact earliest-start timing, so the written schedule is
numerically consistent and never slower than the MILP's own solution. If CBC
returns no incumbent within the limit, the lockstep schedule is written so
the output is always a valid schedule.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple

import pulp

from data.collectives import EXPERIMENTS, ExperimentSpec, load_instance, mb_per_us

_PROCESS_START = time.monotonic()

Volumes = Dict[Tuple[int, int], float]


def horizon_us(spec: ExperimentSpec) -> float:
    bandwidth = mb_per_us(spec.per_link_gbps)
    return (
        sum(step.message_mb / bandwidth + spec.base_latency_us for step in spec.steps)
        + len(spec.steps) * spec.reconfig_latency_us
        + 1_000.0
    )


def lockstep_cct_us(spec: ExperimentSpec) -> float:
    bandwidth = mb_per_us(spec.per_link_gbps)
    changes = sum(1 for prev, cur in zip(spec.steps, spec.steps[1:]) if prev.config != cur.config)
    return (
        sum(step.message_mb / (spec.optical_degree * bandwidth) + spec.base_latency_us for step in spec.steps)
        + changes * spec.reconfig_latency_us
    )


def build_model(spec: ExperimentSpec, big_m: str = "lockstep") -> Dict:
    """The SWOT MILP (paper Eqs. 1-11) with big-M linearization.

    The paper leaves the big-M constant unspecified. ``big_m="lockstep"``
    (default) sets M to the lockstep (Strawman-ICR) completion time and bounds
    CCT by it: the lockstep schedule is a feasible point of the MILP, so the
    optimum is unchanged, while the time-limited solver never returns a
    schedule slower than lockstep. ``"horizon"`` is the loose sum-of-everything
    horizon used by earlier iterations (kept for comparison).
    """
    steps = spec.steps
    n_steps = len(steps)
    k = spec.optical_degree
    planes = range(k)
    idxs = range(n_steps)
    bandwidth = mb_per_us(spec.per_link_gbps)
    horizon = horizon_us(spec) if big_m == "horizon" else lockstep_cct_us(spec) + 1.0

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
        # Eq. 1: traffic conservation over the planes used in this step.
        model += pulp.lpSum(data[i][j] for j in planes) == step.message_mb
        for j in planes:
            model += data[i][j] <= step.message_mb * use[i][j]
            model += data[i][j] >= 1e-6 * use[i][j]
            model += reconfig[i][j] <= use[i][j]
            # Eq. 2: alpha-beta transmission time.
            model += t_end[i][j] - t_start[i][j] == data[i][j] / bandwidth + spec.base_latency_us * use[i][j]
            # Eq. 3: reconfiguration duration.
            model += r_end[i][j] - r_start[i][j] == spec.reconfig_latency_us * reconfig[i][j]
            # Eq. 8-9: per-plane serial use and circuit readiness.
            model += r_start[i][j] >= prev_free[i][j]
            model += t_start[i][j] >= r_end[i][j]
            # Eq. 11: logical step barrier.
            if i > 0:
                model += t_start[i][j] >= step_end[i - 1]
            # Eq. 10: step completion.
            model += step_end[i] >= t_end[i][j] - horizon * (1 - use[i][j])

            if i == 0:
                # Eq. 6: planes start free and pre-configured for their first use.
                model += prev_free[i][j] == 0
                model += reconfig[i][j] == 0
            else:
                # Eq. 7: previous activity on this plane.
                model += prev_free[i][j] >= prev_free[i - 1][j]
                model += prev_free[i][j] >= t_end[i - 1][j] - horizon * (1 - use[i - 1][j])
                model += prev_free[i][j] >= r_end[i - 1][j] - horizon * (1 - reconfig[i - 1][j])

                # Eq. 4-5 (last_cfg / s_ij): the most recent previous use of the
                # plane fixes its current topology. If an intervening use
                # exists the implication is relaxed, so skipped steps model
                # topology bypassing.
                for prev in range(i):
                    intervening = pulp.lpSum(use[h][j] for h in range(prev + 1, i))
                    if steps[prev].config == step.config:
                        model += reconfig[i][j] <= 2 - use[i][j] - use[prev][j] + intervening
                    else:
                        model += reconfig[i][j] >= use[i][j] + use[prev][j] - intervening - 1

        if i > 0:
            model += step_end[i] >= step_end[i - 1]
    model += cct >= step_end[n_steps - 1]
    if big_m == "lockstep":
        model += cct <= horizon

    return {
        "model": model,
        "use": use,
        "reconfig": reconfig,
        "data": data,
        "cct": cct,
        "n_steps": n_steps,
        "k": k,
    }


def cbc(time_limit_s: float, seed: int, warm_start: bool = False) -> pulp.PULP_CBC_CMD:
    kwargs = {
        "msg": False,
        "timeLimit": max(1.0, float(time_limit_s)),
        "options": [f"randomSeed {seed}", f"randomCbcSeed {seed}"],
    }
    if warm_start:
        kwargs["warmStart"] = True
    return pulp.PULP_CBC_CMD(**kwargs)


def has_incumbent(model: pulp.LpProblem, status_code: int) -> bool:
    """True when CBC returned an integer-feasible solution."""
    sol_status = getattr(model, "sol_status", None)
    if sol_status is not None:
        return sol_status in (1, 2)  # LpSolutionOptimal, LpSolutionIntegerFeasible
    return status_code == 1


def extract_volumes(spec: ExperimentSpec, milp: Dict) -> Volumes | None:
    """Read the MILP's plane-use pattern and message split; None if no incumbent."""
    volumes: Volumes = {}
    for i, step in enumerate(spec.steps):
        chosen = {}
        for j in range(milp["k"]):
            u = milp["use"][i][j].varValue
            d = milp["data"][i][j].varValue
            if u is None or d is None:
                return None
            if u > 0.5 and d > 1e-9:
                chosen[j] = float(d)
        total = sum(chosen.values())
        if not chosen or total <= 0:
            return None
        for j, d in chosen.items():
            volumes[(i, j)] = d * step.message_mb / total
    return volumes


def lockstep_volumes(spec: ExperimentSpec) -> Volumes:
    k = spec.optical_degree
    return {(i, j): step.message_mb / k for i, step in enumerate(spec.steps) for j in range(k)}


def build_schedule(spec: ExperimentSpec, volumes: Volumes) -> List[Dict]:
    """Earliest-start timing for a fixed plane-use pattern and split.

    Every constraint is a precedence (>=), so starting each activity as early
    as allowed is component-wise optimal for the given decisions.
    """
    bandwidth = mb_per_us(spec.per_link_gbps)
    plane_free: Dict[int, float] = {}
    plane_config: Dict[int, int] = {}
    previous_step_end = 0.0
    schedule = []
    for i, step in enumerate(spec.steps):
        step_end = previous_step_end
        for j in range(spec.optical_degree):
            if (i, j) not in volumes:
                continue
            volume = volumes[(i, j)]
            switch = j in plane_config and plane_config[j] != step.config
            r_start = plane_free.get(j, 0.0)
            r_end = r_start + (spec.reconfig_latency_us if switch else 0.0)
            t_start = max(previous_step_end, r_end)
            t_end = t_start + volume / bandwidth + spec.base_latency_us
            schedule.append(
                {
                    "step": step.step,
                    "config": step.config,
                    "plane": j,
                    "message_mb": volume,
                    "reconfigured": int(switch),
                    "reconfig_start_us": r_start,
                    "reconfig_end_us": r_end,
                    "transmit_start_us": t_start,
                    "transmit_end_us": t_end,
                }
            )
            plane_free[j] = t_end
            plane_config[j] = step.config
            step_end = max(step_end, t_end)
        previous_step_end = step_end
    return schedule


def schedule_cct(schedule: List[Dict]) -> float:
    return max(item["transmit_end_us"] for item in schedule)


def solve_swot(spec: ExperimentSpec, time_limit_s: float = 120, seed: int = 1, big_m: str = "lockstep") -> Dict:
    started = time.monotonic()
    milp = build_model(spec, big_m=big_m)
    remaining = time_limit_s - (time.monotonic() - started)
    status = "Not Solved"
    volumes = None
    objective = None
    try:
        code = milp["model"].solve(cbc(remaining, seed))
        status = pulp.LpStatus.get(code, str(code))
        if has_incumbent(milp["model"], code):
            volumes = extract_volumes(spec, milp)
            objective = milp["cct"].varValue
    except Exception as exc:  # CBC crash or missing binary: keep a valid output
        status = f"solver error: {type(exc).__name__}: {exc}"
    fallback = volumes is None
    if fallback:
        volumes = lockstep_volumes(spec)
    schedule = build_schedule(spec, volumes)
    events = sum(item["reconfigured"] for item in schedule)
    return {
        "method": "swot",
        "experiment": spec.name,
        "solver_status": status,
        "milp_objective_us": objective,
        "fallback_lockstep": fallback,
        "cct_us": schedule_cct(schedule),
        "reconfiguration_events": int(events),
        "schedule": schedule,
    }


def solve_instance_file(instance: Path, output: Path, time_limit_s: float, seed: int, big_m: str = "lockstep") -> None:
    spec = load_instance(instance)
    budget = time_limit_s - (time.monotonic() - _PROCESS_START)
    result = solve_swot(spec, time_limit_s=budget, seed=seed, big_m=big_m)
    output.write_text(json.dumps(result))


def run(output_dir: Path, time_limit_s: int, seed: int = 1) -> None:
    """Batch mode over the paper's named instances (for inspection)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {"experiments": {}}
    for name, factory in EXPERIMENTS.items():
        spec = factory()
        payload["experiments"][name] = {
            "spec": spec.to_json(),
            "results": {"swot": solve_swot(spec, time_limit_s=time_limit_s, seed=seed)},
        }
    (output_dir / "swot_results.json").write_text(json.dumps(payload, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", help="instance JSON (single-instance solver mode)")
    parser.add_argument("--output", help="schedule JSON to write (single-instance solver mode)")
    parser.add_argument("--output-dir", default="checkpoints/swot", help="batch mode output directory")
    parser.add_argument("--time-limit-s", type=float, default=120)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--big-m", choices=["horizon", "lockstep"], default="lockstep")
    args = parser.parse_args()
    if args.instance:
        if not args.output:
            parser.error("--output is required with --instance")
        solve_instance_file(Path(args.instance), Path(args.output), args.time_limit_s, args.seed, args.big_m)
    else:
        run(Path(args.output_dir), int(args.time_limit_s), args.seed)


if __name__ == "__main__":
    main()

"""SWOT MILP scheduler reproduction.

This implements the paper's core computation (Section 3.2): a mixed-integer
linear program that jointly chooses heterogeneous message splits (d_ij),
per-plane asynchronous reconfiguration times, and topology bypassing (r_ij,
u_ij) to minimize the collective completion time, solved with CBC via PuLP.

Solver budget. The paper gives CBC a 120 s time limit. A time limit makes the
returned schedule depend on the machine and on whatever else runs beside it
(PuLP's CBC time limit is wall-clock, and CBC's heuristics also scale their
effort with the time left), so the reproduction gives CBC a deterministic work
budget instead and passes CBC no time limit at all: a number of
branch-and-bound nodes per instance (``method/budget.json``: ``cbc_max_nodes``
for collectives of up to ``full_budget_max_steps`` steps, scaled by
(max_steps / steps)^2 beyond that, because CBC's node rate falls about that
fast with the number of steps), CBC's default single-threaded search, fixed
seeds. The budget was calibrated once on the reference compute node so that
CBC uses well under the evaluator's 120 CPU-seconds; the schedule is then the
same on any machine and under any load. The only other stop is a safety stop
on CPU time (an RLIMIT_CPU on the CBC process, ``SAFETY_MARGIN_S`` below the
CPU budget the evaluator passes) that never binds for the reference; if it
ever did, CBC would be killed and the lockstep schedule written.

Solver interface (used by every evaluator through scripts/solvers/swot.sh):

    python -m method.swot_scheduler --instance IN.json --output OUT.json --time-limit-s 120

The MILP's discrete decisions (which planes carry which volume in each step)
are serialized with exact earliest-start timing, so the written schedule is
numerically consistent and never slower than the MILP's own solution. If CBC
returns no incumbent within its node budget, the lockstep schedule is written
so the output is always a valid schedule.
"""

from __future__ import annotations

import argparse
import json
import resource
from pathlib import Path
from typing import Dict, List, Tuple

import pulp

from data.collectives import EXPERIMENTS, ExperimentSpec, load_instance, mb_per_us

BUDGET_FILE = Path(__file__).resolve().parent / "budget.json"
SAFETY_MARGIN_S = 8.0  # CPU-seconds kept free of the evaluator's budget for model building and output

Volumes = Dict[Tuple[int, int], float]


def default_max_nodes(spec: ExperimentSpec | None = None) -> int:
    """The calibrated deterministic CBC node budget for ``spec``."""
    try:
        budget = json.loads(BUDGET_FILE.read_text())
        nodes = int(budget["cbc_max_nodes"])
        max_steps = int(budget.get("full_budget_max_steps", 0))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(f"cannot read the CBC node budget from {BUDGET_FILE}: {exc}") from None
    if spec is None or not max_steps or len(spec.steps) <= max_steps:
        return nodes
    return max(100, int(nodes * (max_steps / len(spec.steps)) ** 2))


def cpu_used_s() -> float:
    """CPU-seconds used so far by this process and its finished children."""
    me = resource.getrusage(resource.RUSAGE_SELF)
    kids = resource.getrusage(resource.RUSAGE_CHILDREN)
    return me.ru_utime + me.ru_stime + kids.ru_utime + kids.ru_stime


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


def build_model(spec: ExperimentSpec, big_m: str = "lockstep", formulation: str = "pairwise") -> Dict:
    """The SWOT MILP (paper Eqs. 1-11) with big-M linearization.

    ``formulation="pairwise"`` (default) encodes topology bypassing (Eqs. 4-5)
    as "the most recent previous use of a plane fixes its topology", an
    O(n^2 k) set of implications. ``"paper"`` uses the paper's own variables:
    ``last_cfg_ij`` (the topology plane j holds before step i, carried forward
    and set to ``cfg_i`` when the plane is used) and ``s_ij`` (it matches step
    i), with each plane's initial topology free (planes are configured before
    the collective starts, as in Fig. 5). Both have the same optimum; with
    CBC the paper's encoding was about 2x slower per node and found no better
    incumbents in a node-limited probe, so the pairwise one is the default.

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
    if formulation == "paper":
        max_cfg = max(step.config for step in steps)
        cfg_m = float(max_cfg + 1)
        last_cfg = pulp.LpVariable.dicts("last_cfg", (idxs, planes), 0, max_cfg)
        same = pulp.LpVariable.dicts("s", (idxs, planes), 0, 1, cat="Binary")
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
            if formulation == "paper":
                # Eq. 4: a used plane whose topology does not match must reconfigure.
                model += reconfig[i][j] >= use[i][j] - same[i][j]
                # Eq. 5: |cfg_i - last_cfg_ij| <= M (1 - s_ij).
                model += step.config - last_cfg[i][j] <= cfg_m * (1 - same[i][j])
                model += last_cfg[i][j] - step.config <= cfg_m * (1 - same[i][j])
                # last_cfg after step i: cfg_i if the plane is used, else unchanged.
                if i + 1 < n_steps:
                    model += last_cfg[i + 1][j] - step.config <= cfg_m * (1 - use[i][j])
                    model += step.config - last_cfg[i + 1][j] <= cfg_m * (1 - use[i][j])
                    model += last_cfg[i + 1][j] - last_cfg[i][j] <= cfg_m * use[i][j]
                    model += last_cfg[i][j] - last_cfg[i + 1][j] <= cfg_m * use[i][j]
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

                # Pairwise encoding of Eqs. 4-5: the most recent previous use of
                # the plane fixes its current topology. If an intervening use
                # exists the implication is relaxed, so skipped steps model
                # topology bypassing.
                for prev in (range(i) if formulation == "pairwise" else ()):
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


def cbc(seed: int, max_nodes: int | None = None, warm_start: bool = False,
        log_path: str | None = None) -> pulp.PULP_CBC_CMD:
    """CBC (default single-threaded search) with fixed seeds and an optional node budget.

    No time limit is passed to CBC (no ``-sec``), so nothing in CBC's search
    depends on the clock; CBC's clock is set to CPU time (PuLP otherwise
    passes ``timeMode elapsed``), so even its log never reads the wall clock.
    Bound CBC's CPU time with ``cpu_cap`` around the solve instead (a kill
    switch outside the solver, not a search parameter).
    """
    kwargs = {
        "msg": False,
        "timeMode": "cpu",
        "options": [f"randomSeed {seed}", f"randomCbcSeed {seed}"],
    }
    if max_nodes:
        kwargs["maxNodes"] = int(max_nodes)
    if warm_start:
        kwargs["warmStart"] = True
    if log_path:
        kwargs["logPath"] = log_path
    return pulp.PULP_CBC_CMD(**kwargs)


class cpu_cap:
    """Safety stop: CBC processes started inside this block are killed after ``seconds`` CPU-seconds.

    Sets the soft RLIMIT_CPU (inherited by child processes; counted per
    process) and disables core dumps; restores both on exit. A killed CBC makes
    PuLP raise, and callers fall back to a valid schedule.
    """

    def __init__(self, seconds: float):
        self.seconds = max(1, int(seconds))

    def __enter__(self):
        self.saved_cpu = resource.getrlimit(resource.RLIMIT_CPU)
        self.saved_core = resource.getrlimit(resource.RLIMIT_CORE)
        hard = self.saved_cpu[1]
        soft = self.seconds if hard == resource.RLIM_INFINITY else min(self.seconds, hard)
        # The cap also applies to this process: never set it below what it has already used.
        own = resource.getrusage(resource.RUSAGE_SELF)
        soft = max(soft, int(own.ru_utime + own.ru_stime) + 2)
        if hard != resource.RLIM_INFINITY:
            soft = min(soft, hard)
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
        resource.setrlimit(resource.RLIMIT_CORE, (0, self.saved_core[1]))
        return self

    def __exit__(self, *exc):
        resource.setrlimit(resource.RLIMIT_CPU, self.saved_cpu)
        resource.setrlimit(resource.RLIMIT_CORE, self.saved_core)
        return False


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


def solve_swot(spec: ExperimentSpec, time_limit_s: float = 120, seed: int = 1, big_m: str = "lockstep",
               max_nodes: int | None = None, log_path: str | None = None) -> Dict:
    """Solve the SWOT MILP. ``max_nodes`` is the deterministic work budget (default:
    ``method/budget.json``); ``time_limit_s`` is the CPU-time budget left for this
    call and only sets the safety stop (it never reaches CBC as a time limit)."""
    started = cpu_used_s()
    if not max_nodes:
        max_nodes = default_max_nodes(spec)
    milp = build_model(spec, big_m=big_m)
    cap = time_limit_s - (cpu_used_s() - started) - SAFETY_MARGIN_S
    status = "Not Solved"
    volumes = None
    objective = None
    try:
        with cpu_cap(cap):
            code = milp["model"].solve(cbc(seed, max_nodes=max_nodes, log_path=log_path))
        status = pulp.LpStatus.get(code, str(code))
        if has_incumbent(milp["model"], code):
            volumes = extract_volumes(spec, milp)
            objective = milp["cct"].varValue
    except Exception as exc:  # CBC crash, safety stop or missing binary: keep a valid output
        status = f"solver error: {type(exc).__name__}: {exc}"
    fallback = volumes is None
    if fallback:
        volumes = lockstep_volumes(spec)
    schedule = build_schedule(spec, volumes)
    events = sum(item["reconfigured"] for item in schedule)
    return {
        "method": "swot",
        "experiment": spec.name,
        "cbc_max_nodes": max_nodes,
        "cpu_s": round(cpu_used_s() - started, 3),
        "solver_status": status,
        "milp_objective_us": objective,
        "fallback_lockstep": fallback,
        "cct_us": schedule_cct(schedule),
        "reconfiguration_events": int(events),
        "schedule": schedule,
    }


def solve_instance_file(instance: Path, output: Path, time_limit_s: float, seed: int, big_m: str = "lockstep",
                        max_nodes: int | None = None, log_path: str | None = None) -> None:
    spec = load_instance(instance)
    budget = time_limit_s - cpu_used_s()
    result = solve_swot(spec, time_limit_s=budget, seed=seed, big_m=big_m, max_nodes=max_nodes, log_path=log_path)
    output.write_text(json.dumps(result))


def run(output_dir: Path, time_limit_s: int, seed: int = 1) -> None:
    """Batch mode over the paper's named instances (for inspection)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {"experiments": {}}
    for name, factory in EXPERIMENTS.items():
        spec = factory()
        payload["experiments"][name] = {
            "spec": spec.to_json(),
            "results": {"swot": solve_swot(spec, time_limit_s=time_limit_s, seed=seed,
                                           max_nodes=default_max_nodes(spec))},
        }
    (output_dir / "swot_results.json").write_text(json.dumps(payload, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", help="instance JSON (single-instance solver mode)")
    parser.add_argument("--output", help="schedule JSON to write (single-instance solver mode)")
    parser.add_argument("--output-dir", default="checkpoints/swot", help="batch mode output directory")
    parser.add_argument("--time-limit-s", type=float, default=120,
                        help="CPU-seconds budget for this call (sets only the CPU safety stop; never a CBC time limit)")
    parser.add_argument("--max-nodes", type=int, default=None,
                        help="CBC node budget (default: method/budget.json)")
    parser.add_argument("--node-scale", type=float, default=1.0,
                        help="multiply the default node budget (budget-sensitivity variants)")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--big-m", choices=["horizon", "lockstep"], default="lockstep")
    parser.add_argument("--cbc-log", default=None, help="write the CBC log here (calibration)")
    args = parser.parse_args()
    if args.instance:
        if not args.output:
            parser.error("--output is required with --instance")
        if args.max_nodes is None:
            max_nodes = max(1, int(default_max_nodes(load_instance(Path(args.instance))) * args.node_scale))
        elif args.max_nodes > 0:
            max_nodes = args.max_nodes
        else:
            parser.error("--max-nodes must be positive (CBC gets no time limit, so the node budget is its only stop)")
        solve_instance_file(Path(args.instance), Path(args.output), args.time_limit_s, args.seed, args.big_m,
                            max_nodes=max_nodes, log_path=args.cbc_log)
    else:
        run(Path(args.output_dir), int(args.time_limit_s), args.seed)


if __name__ == "__main__":
    main()

"""Hidden-test evaluator: runs every solver on disk on held-out instances.

The instances live only in ``eval/test/instances.json``. For each method
``scripts/solvers/<method>.sh`` the evaluator writes one instance at a time to
a private temporary directory, runs

    bash scripts/solvers/<method>.sh INSTANCE.json OUTPUT.json CPU_BUDGET_S

and scores only the serialized schedule. The budget is CPU time counted by
this evaluator over the solver's whole process tree (every descendant is
reaped here, including ones that leave the process group), not wall-clock
time: a solver that uses more than ``CPU_BUDGET_S`` CPU-seconds on an instance
fails. A wall-clock cap only stops hung or sleeping solvers. Every number is
recomputed here from the schedule against the frozen instance; any scalar,
flag or specification the solver writes is ignored. The comparison baseline
(lockstep Strawman-ICR) is computed here from the frozen instance.

A run fails as a whole if any instance is missing, late, malformed or physically
infeasible; a failed run receives the worst value of every scored metric in
every experiment. The method key ``swot`` is always reported (missing solver =
failed run). This module never imports method code.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SLICE_NAME = "test"
INSTANCES_PATH = HERE / "instances.json"
SOLVERS_DIR = ROOT / "scripts" / "solvers"
CPU_BUDGET_S = 120  # the source paper's per-instance solver budget, as counted CPU-seconds
CPU_TOLERANCE_S = 1.0
WALL_CAP_S = 2 * CPU_BUDGET_S + 60  # only stops hung or sleeping solvers
REQUIRED_METHODS = ("swot",)
BASELINE_METHOD = "strawman_icr"
PRIMARY = "cct_reduction_vs_strawman_pct"
WORST_ROW = {PRIMARY: -100.0, "valid_schedule": 0.0}
REDUCTION_FLOOR = -100.0
REDUCTION_CEIL = 100.0
MAX_OUTPUT_BYTES = 64 * 1024 * 1024


class InvalidSchedule(Exception):
    pass


# ---------------------------------------------------------------------------
# Frozen instances and the fixed comparison side.
# ---------------------------------------------------------------------------


def load_suite() -> dict[str, list[dict[str, Any]]]:
    payload = json.loads(INSTANCES_PATH.read_text())
    return {name: list(items) for name, items in payload["experiments"].items()}


def bandwidth_mb_per_us(instance: dict[str, Any]) -> float:
    return float(instance["per_link_gbps"]) / 8000.0


def strawman_cct_us(instance: dict[str, Any]) -> float:
    """Lockstep ICR: all planes per step, even split, one global switch per topology change."""
    k = int(instance["optical_degree"])
    bw = bandwidth_mb_per_us(instance)
    lat = float(instance["base_latency_us"])
    recfg = float(instance["reconfig_latency_us"])
    total = 0.0
    previous = None
    for step in instance["steps"]:
        volume = float(step["message_mb"])
        if previous is not None and int(step["config"]) != previous:
            total += recfg
        total += volume / (k * bw) + (lat if volume > 0 else 0.0)
        previous = int(step["config"])
    return total


def lower_bound_cct_us(instance: dict[str, Any]) -> float:
    """No schedule can beat all k planes per step with no switching at all."""
    k = int(instance["optical_degree"])
    bw = bandwidth_mb_per_us(instance)
    lat = float(instance["base_latency_us"])
    return sum(float(s["message_mb"]) / (k * bw) + lat for s in instance["steps"])


# ---------------------------------------------------------------------------
# Physical validation of a serialized schedule.
# ---------------------------------------------------------------------------


def _number(value: Any, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidSchedule(f"{what} is not a number")
    number = float(value)
    if not math.isfinite(number):
        raise InvalidSchedule(f"{what} is not finite")
    return number


def _integer(value: Any, what: str) -> int:
    number = _number(value, what)
    if number != int(number):
        raise InvalidSchedule(f"{what} is not an integer")
    return int(number)


def schedule_cct_us(instance: dict[str, Any], output: Any) -> float:
    """Return the completion time of a physically valid schedule, else raise."""
    if not isinstance(output, dict):
        raise InvalidSchedule("output is not a JSON object")
    schedule = output.get("schedule")
    if not isinstance(schedule, list) or not schedule:
        raise InvalidSchedule("missing or empty schedule")

    k = int(instance["optical_degree"])
    bw = bandwidth_mb_per_us(instance)
    lat = float(instance["base_latency_us"])
    recfg = float(instance["reconfig_latency_us"])
    steps = instance["steps"]
    position = {int(step["step"]): idx for idx, step in enumerate(steps)}
    scale = strawman_cct_us(instance)
    tol = 1e-3 + 1e-6 * scale

    per_step: list[list[dict[str, Any]]] = [[] for _ in steps]
    seen: set[tuple[int, int]] = set()
    for raw in schedule:
        if not isinstance(raw, dict):
            raise InvalidSchedule("schedule entry is not an object")
        try:
            step_id = _integer(raw["step"], "step")
            plane = _integer(raw["plane"], "plane")
            volume = _number(raw["message_mb"], "message_mb")
            t_start = _number(raw["transmit_start_us"], "transmit_start_us")
            t_end = _number(raw["transmit_end_us"], "transmit_end_us")
        except KeyError as exc:
            raise InvalidSchedule(f"schedule entry lacks {exc}") from None
        if step_id not in position:
            raise InvalidSchedule("unknown step")
        if not 0 <= plane < k:
            raise InvalidSchedule("plane index outside the fixed optical degree")
        if (step_id, plane) in seen:
            raise InvalidSchedule("duplicate (step, plane) entry")
        seen.add((step_id, plane))
        if volume <= 0.0:
            raise InvalidSchedule("non-positive message volume")
        if t_start < -tol:
            raise InvalidSchedule("activity before the collective starts")
        idx = position[step_id]
        config = int(steps[idx]["config"])
        if "config" in raw and raw["config"] is not None and _integer(raw["config"], "config") != config:
            raise InvalidSchedule("entry topology differs from the step's required topology")
        if t_end - t_start < volume / bw + lat - tol:
            raise InvalidSchedule("transmission shorter than message/bandwidth + base latency")
        per_step[idx].append(
            {"plane": plane, "volume": volume, "start": t_start, "end": t_end, "raw": raw}
        )

    previous_step_end = 0.0
    for idx, step in enumerate(steps):
        items = per_step[idx]
        required = float(step["message_mb"])
        if not items:
            raise InvalidSchedule("a step has no transmissions")
        delivered = sum(item["volume"] for item in items)
        if abs(delivered - required) > 1e-6 * max(1.0, required):
            raise InvalidSchedule("step volume not conserved")
        if min(item["start"] for item in items) < previous_step_end - tol:
            raise InvalidSchedule("step starts before the previous step finished")
        previous_step_end = max(item["end"] for item in items)

    plane_config: dict[int, int] = {}
    plane_free: dict[int, float] = {}
    for idx, step in enumerate(steps):
        config = int(step["config"])
        for item in sorted(per_step[idx], key=lambda entry: entry["plane"]):
            plane = item["plane"]
            raw = item["raw"]
            needs_switch = plane in plane_config and plane_config[plane] != config
            flag = raw.get("reconfigured")
            if flag is not None:
                if isinstance(flag, bool):
                    flag_value = int(flag)
                else:
                    flag_value = _integer(flag, "reconfigured")
                if flag_value not in (0, 1) or bool(flag_value) != needs_switch:
                    raise InvalidSchedule("reconfiguration flag inconsistent with the plane's topology sequence")
            if needs_switch:
                try:
                    r_start = _number(raw["reconfig_start_us"], "reconfig_start_us")
                    r_end = _number(raw["reconfig_end_us"], "reconfig_end_us")
                except KeyError as exc:
                    raise InvalidSchedule(f"required reconfiguration lacks {exc}") from None
                if r_start < plane_free[plane] - tol:
                    raise InvalidSchedule("plane switches while still transmitting")
                if r_end - r_start < recfg - tol:
                    raise InvalidSchedule("reconfiguration shorter than the switching latency")
                if item["start"] < r_end - tol:
                    raise InvalidSchedule("transmission before the circuit is ready")
            elif plane in plane_free and item["start"] < plane_free[plane] - tol:
                raise InvalidSchedule("overlapping activities on one plane")
            plane_config[plane] = config
            plane_free[plane] = item["end"]

    cct = max(item["end"] for items in per_step for item in items)
    if cct < lower_bound_cct_us(instance) - tol:
        raise InvalidSchedule("completion time below the physical lower bound")
    return cct


def reduction_pct(strawman: float, cct: float) -> float:
    value = 100.0 * (strawman - cct) / strawman
    return min(REDUCTION_CEIL, max(REDUCTION_FLOOR, value))


# ---------------------------------------------------------------------------
# Running solvers.
# ---------------------------------------------------------------------------


def discover_methods() -> list[str]:
    names = set(REQUIRED_METHODS)
    if SOLVERS_DIR.is_dir():
        for path in SOLVERS_DIR.glob("*.sh"):
            if path.is_file():
                names.add(path.stem)
    names.discard(BASELINE_METHOD)
    return sorted(names)


def _become_subreaper() -> None:
    """Orphaned solver descendants are re-parented to (and reaped by) this process."""
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        libc.prctl(36, 1, 0, 0, 0)  # PR_SET_CHILD_SUBREAPER
    except (OSError, AttributeError):
        pass


def _kill_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def _children_of_self() -> list[int]:
    me = os.getpid()
    kids = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat") as handle:
                fields = handle.read().rsplit(")", 1)[1].split()
        except (OSError, IndexError):
            continue
        if len(fields) > 1 and fields[1] == str(me):
            kids.append(int(entry))
    return kids


def _reap_strays() -> None:
    """Kill and reap every remaining descendant so its CPU time is counted."""
    for _ in range(200):
        kids = _children_of_self()
        for pid in kids:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        reaped = False
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                break
            if pid == 0:
                break
            reaped = True
        if not kids and not reaped:
            return
        time.sleep(0.02)


def _children_cpu_s() -> float:
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime


def _limit_cpu() -> None:
    # Per-process backstop; the budget itself is the counted total below.
    soft = int(CPU_BUDGET_S + CPU_TOLERANCE_S) + 2
    resource.setrlimit(resource.RLIMIT_CPU, (soft, soft + 3))


def run_solver(script: Path, instance: dict[str, Any], workdir: Path) -> tuple[Any, str, float]:
    """Run one solver on one instance. Returns (parsed output or None, status, counted CPU-seconds)."""
    public = {key: value for key, value in instance.items() if key not in ("experiment",)}
    instance_path = workdir / "instance.json"
    output_path = workdir / "schedule.json"
    log_path = workdir / "solver.log"
    instance_path.write_text(json.dumps(public))
    _reap_strays()
    cpu_before = _children_cpu_s()
    timed_out = False
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            ["bash", str(script), str(instance_path), str(output_path), str(CPU_BUDGET_S)],
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            preexec_fn=_limit_cpu,
        )
        try:
            returncode = process.wait(timeout=WALL_CAP_S)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_group(process)
            returncode = process.wait()
        finally:
            _kill_group(process)
            _reap_strays()
    cpu = _children_cpu_s() - cpu_before
    if timed_out:
        return None, f"wall-clock cap of {WALL_CAP_S} s exceeded (hung or sleeping solver)", cpu
    if cpu > CPU_BUDGET_S + CPU_TOLERANCE_S:
        return None, f"CPU budget exceeded: {cpu:.1f} s > {CPU_BUDGET_S} s", cpu
    if returncode != 0:
        tail = log_path.read_bytes()[-400:].decode("utf-8", "replace").strip().splitlines()[-3:]
        return None, f"exit code {returncode}: {' | '.join(tail)}", cpu
    if not output_path.is_file():
        return None, "no output file", cpu
    if output_path.stat().st_size > MAX_OUTPUT_BYTES:
        return None, "output too large", cpu
    try:
        return json.loads(output_path.read_text()), "ok", cpu
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None, "unparseable output", cpu


def evaluate_method(method: str, suite: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    script = SOLVERS_DIR / f"{method}.sh"
    reductions: dict[str, list[float]] = {name: [] for name in suite}
    cpu_used: dict[str, float] = {}
    failure = None
    if not script.is_file():
        failure = {"instance": None, "reason": "solver script missing"}
    for experiment, instances in suite.items():
        for instance in instances:
            if failure is not None:
                break
            workdir = Path(tempfile.mkdtemp(prefix="optsched_eval_"))
            cpu = 0.0
            try:
                try:
                    output, status, cpu = run_solver(script, instance, workdir)
                except OSError as exc:
                    output, status = None, f"could not run solver: {type(exc).__name__}"
                if status == "ok":
                    try:
                        cct = schedule_cct_us(instance, output)
                    except InvalidSchedule as exc:
                        status = f"invalid schedule: {exc}"
                    except (TypeError, ValueError, KeyError, AttributeError) as exc:
                        status = f"invalid schedule: {type(exc).__name__}"
            finally:
                shutil.rmtree(workdir, ignore_errors=True)
            if status != "ok":
                failure = {"instance": instance["id"], "reason": status}
                print(f"[eval-{SLICE_NAME}] method={method} instance={instance['id']} status=FAILED "
                      f"cpu_s={cpu:.1f} reason={status}", flush=True)
                break
            value = reduction_pct(strawman_cct_us(instance), cct)
            reductions[experiment].append(value)
            cpu_used[instance["id"]] = round(cpu, 2)
            print(f"[eval-{SLICE_NAME}] method={method} instance={instance['id']} status=ok "
                  f"reduction={value:.6f} cpu_s={cpu:.1f}", flush=True)
    rows = {}
    for experiment, instances in suite.items():
        if failure is not None:
            rows[experiment] = dict(WORST_ROW)
        else:
            values = reductions[experiment]
            rows[experiment] = {PRIMARY: sum(values) / len(values), "valid_schedule": 1.0}
    return {"rows": rows, "failure": failure, "cpu_s": cpu_used}


def evaluate(output: Path) -> dict[str, Any]:
    _become_subreaper()
    suite = load_suite()
    if output.exists():
        output.unlink()
    methods = discover_methods()
    digest = hashlib.sha256(INSTANCES_PATH.read_bytes()).hexdigest()[:16]
    scores: dict[str, Any] = {
        "_metadata": {
            "slice": SLICE_NAME,
            "instance_suite_sha256_16": digest,
            "instances_per_experiment": {name: len(items) for name, items in suite.items()},
            "solver_cpu_budget_s": CPU_BUDGET_S,
            "budget_rule": "CPU-seconds of the solver's whole process tree, counted by the evaluator; over budget = failed instance",
            "wall_clock_cap_s": WALL_CAP_S,
            "methods": methods,
            "failure_rule": "any missing/over-budget/invalid instance fails the whole run: worst value in every metric of every experiment",
        },
        "experiments": {
            name: {"results": {BASELINE_METHOD: {PRIMARY: 0.0, "valid_schedule": 1.0}}, "_status": {}}
            for name in suite
        },
    }
    for method in methods:
        result = evaluate_method(method, suite)
        for experiment, row in result["rows"].items():
            scores["experiments"][experiment]["results"][method] = row
            scores["experiments"][experiment]["_status"][method] = {
                "run_failed": result["failure"] is not None,
                "failure": result["failure"],
                "cpu_s": {iid: result["cpu_s"][iid] for iid in
                          (item["id"] for item in suite[experiment]) if iid in result["cpu_s"]},
            }
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(".tmp")
    tmp.write_text(json.dumps(scores, indent=2))
    tmp.replace(output)
    return scores


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "scoring" / "scores_test.json"))
    args = parser.parse_args()
    evaluate(Path(args.output))


if __name__ == "__main__":
    sys.exit(main())

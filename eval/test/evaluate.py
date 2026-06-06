"""Score the held-out test slice from serialized scheduler artifacts.

The split is by collective stage: test scores the second half of each
Rabenseifner workload. It enumerates method entries from the serialized
artifacts and never imports method code.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SLICE_NAME = "test"
MISSING_CCT_US = 1_000_000_000_000.0


def load_results(artifacts: Path) -> dict[str, Any]:
    merged: dict[str, Any] = {"experiments": {}}
    if not artifacts.exists():
        return merged

    for path in sorted(artifacts.rglob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        for exp_name, exp_payload in payload.get("experiments", {}).items():
            slot = merged["experiments"].setdefault(exp_name, {"results": {}})
            if "spec" in exp_payload and "spec" not in slot:
                slot["spec"] = exp_payload["spec"]
            slot["results"].update(exp_payload.get("results", {}))
    return merged


def artifact_methods(payload: dict[str, Any]) -> dict[str, list[str]]:
    methods_by_exp: dict[str, list[str]] = {}
    for exp_name, exp_payload in payload.get("experiments", {}).items():
        results = exp_payload.get("results", {})
        methods_by_exp[exp_name] = [
            method_name for method_name in results if not method_name.startswith("_")
        ]
    return methods_by_exp


def selected_steps(spec: dict[str, Any]) -> set[int]:
    steps = sorted(int(step["step"]) for step in spec.get("steps", []))
    midpoint = max(1, len(steps) // 2)
    return set(steps[midpoint:])


def score_slice(
    exp_payload: dict[str, Any], selected: set[int], required_methods: list[str]
) -> dict[str, dict[str, float]]:
    spec = exp_payload.get("spec")
    results = exp_payload.get("results", {})
    raw_scores: dict[str, dict[str, float]] = {}

    for method_name in required_methods:
        result = results.get(method_name)
        if result is None:
            raw_scores[method_name] = missing_score()
        else:
            raw_scores[method_name] = score_method(spec, result, selected)

    strawman_cct = raw_scores.get("strawman_icr", {}).get("cct_us")
    if strawman_cct and math.isfinite(strawman_cct) and strawman_cct > 0:
        for method_name, row in raw_scores.items():
            if method_name == "strawman_icr":
                row["cct_reduction_vs_strawman_pct"] = 0.0
            else:
                row["cct_reduction_vs_strawman_pct"] = 100.0 * (
                    strawman_cct - row["cct_us"]
                ) / strawman_cct
    else:
        for row in raw_scores.values():
            row["cct_reduction_vs_strawman_pct"] = 0.0

    return raw_scores


def score_method(
    spec: dict[str, Any] | None, result: dict[str, Any], selected: set[int]
) -> dict[str, float]:
    if spec and result.get("schedule"):
        valid = validate_schedule(spec, result["schedule"])
        row = schedule_slice_metrics(spec, result["schedule"], selected)
        row["valid_schedule"] = 1.0 if valid and row["cct_us"] < MISSING_CCT_US else 0.0
        return row

    if spec and result.get("method") == "strawman_icr":
        return lockstep_slice_score(spec, selected, float(result.get("valid_schedule", 1.0)))

    return {
        "cct_us": float(result.get("cct_us", MISSING_CCT_US)),
        "valid_schedule": float(result.get("valid_schedule", 0.0)),
        "reconfiguration_events": float(result.get("reconfiguration_events", 0.0)),
        "step_volume_error_mb": float(result.get("step_volume_error_mb", MISSING_CCT_US)),
        "max_plane_overlap_us": float(result.get("max_plane_overlap_us", MISSING_CCT_US)),
    }


def missing_score() -> dict[str, float]:
    return {
        "cct_us": MISSING_CCT_US,
        "valid_schedule": 0.0,
        "reconfiguration_events": MISSING_CCT_US,
        "step_volume_error_mb": MISSING_CCT_US,
        "max_plane_overlap_us": MISSING_CCT_US,
    }


def schedule_slice_metrics(
    spec: dict[str, Any], schedule: list[dict[str, Any]], selected: set[int]
) -> dict[str, float]:
    items = [item for item in schedule if int(item["step"]) in selected]
    if not items:
        return missing_score()

    starts = []
    ends = []
    activities_by_plane: dict[int, list[tuple[float, float]]] = {}
    reconfiguration_events = 0
    for item in items:
        plane = int(item["plane"])
        if int(item.get("reconfigured", 0)):
            reconfiguration_events += 1
            starts.append(float(item.get("reconfig_start_us", item["transmit_start_us"])))
            activities_by_plane.setdefault(plane, []).append(
                (float(item["reconfig_start_us"]), float(item["reconfig_end_us"]))
            )
        else:
            starts.append(float(item["transmit_start_us"]))
        activities_by_plane.setdefault(plane, []).append(
            (float(item["transmit_start_us"]), float(item["transmit_end_us"]))
        )
        ends.append(float(item["transmit_end_us"]))
    return {
        "cct_us": max(ends) - min(starts),
        "reconfiguration_events": float(reconfiguration_events),
        "step_volume_error_mb": slice_volume_error_mb(spec, items, selected),
        "max_plane_overlap_us": max_plane_overlap_us(activities_by_plane),
    }


def slice_volume_error_mb(
    spec: dict[str, Any], items: list[dict[str, Any]], selected: set[int]
) -> float:
    tolerance = 1e-4
    observed: dict[int, float] = {}
    for item in items:
        observed[int(item["step"])] = observed.get(int(item["step"]), 0.0) + float(item["message_mb"])
    error = 0.0
    for step in spec.get("steps", []):
        step_id = int(step["step"])
        if step_id in selected:
            delta = abs(observed.get(step_id, 0.0) - float(step["message_mb"]))
            if delta > tolerance:
                error += delta
    return error


def max_plane_overlap_us(activities_by_plane: dict[int, list[tuple[float, float]]]) -> float:
    worst = 0.0
    for activities in activities_by_plane.values():
        activities.sort()
        for (_, prev_end), (cur_start, _) in zip(activities, activities[1:]):
            worst = max(worst, prev_end - cur_start)
    return max(0.0, worst)


def lockstep_slice_score(
    spec: dict[str, Any], selected: set[int], valid_schedule: float
) -> dict[str, float]:
    bandwidth = float(spec["per_link_gbps"]) / 8_000.0
    optical_degree = float(spec["optical_degree"])
    base_latency_us = float(spec.get("base_latency_us", 0.0))
    reconfig_latency_us = float(spec["reconfig_latency_us"])
    all_steps = sorted(spec.get("steps", []), key=lambda item: int(item["step"]))
    steps = [step for step in all_steps if int(step["step"]) in selected]
    if not steps:
        return missing_score()

    cct = 0.0
    first_selected_index = all_steps.index(steps[0])
    previous_config = (
        int(all_steps[first_selected_index - 1]["config"]) if first_selected_index > 0 else None
    )
    reconfiguration_events = 0
    for step in steps:
        message_mb = float(step["message_mb"])
        cct += message_mb / (optical_degree * bandwidth)
        if message_mb > 0:
            cct += base_latency_us
        current_config = int(step["config"])
        if previous_config is not None and current_config != previous_config:
            cct += reconfig_latency_us
            reconfiguration_events += 1
        previous_config = current_config
    return {
        "cct_us": cct,
        "valid_schedule": valid_schedule,
        "reconfiguration_events": float(reconfiguration_events),
        "step_volume_error_mb": 0.0,
        "max_plane_overlap_us": 0.0,
    }


def validate_schedule(spec: dict[str, Any], schedule: list[dict[str, Any]]) -> bool:
    steps = spec.get("steps", [])
    if not steps or not schedule:
        return False
    tolerance = 1e-4
    by_step: dict[int, list[dict[str, Any]]] = {}
    by_plane: dict[int, list[dict[str, Any]]] = {}
    for item in schedule:
        by_step.setdefault(int(item["step"]), []).append(item)
        by_plane.setdefault(int(item["plane"]), []).append(item)
        if float(item["transmit_start_us"]) + tolerance < float(item["reconfig_end_us"]):
            return False
        if int(item.get("reconfigured", 0)):
            duration = float(item["reconfig_end_us"]) - float(item["reconfig_start_us"])
            if abs(duration - float(spec["reconfig_latency_us"])) > tolerance:
                return False

    previous_step_end = 0.0
    for step in steps:
        step_id = int(step["step"])
        items = by_step.get(step_id, [])
        if not items:
            return False
        if any(int(item["config"]) != int(step["config"]) for item in items):
            return False
        volume = sum(float(item["message_mb"]) for item in items)
        if abs(volume - float(step["message_mb"])) > tolerance:
            return False
        if any(float(item["transmit_start_us"]) + tolerance < previous_step_end for item in items):
            return False
        previous_step_end = max(float(item["transmit_end_us"]) for item in items)

    for items in by_plane.values():
        items.sort(key=lambda item: (int(item["step"]), float(item["transmit_start_us"])))
        previous_config = None
        activities = []
        for item in items:
            current_config = int(item["config"])
            reconfigured = int(item.get("reconfigured", 0))
            if previous_config is not None:
                if current_config == previous_config and reconfigured:
                    return False
                if current_config != previous_config and not reconfigured:
                    return False
            previous_config = current_config
            if reconfigured:
                activities.append((float(item["reconfig_start_us"]), float(item["reconfig_end_us"])))
            activities.append((float(item["transmit_start_us"]), float(item["transmit_end_us"])))
        activities.sort()
        for (_, prev_end), (cur_start, _) in zip(activities, activities[1:]):
            if cur_start + tolerance < prev_end:
                return False
    return True


def evaluate(artifacts: Path, output: Path) -> dict[str, Any]:
    payload = load_results(artifacts)
    required = artifact_methods(payload)
    scores: dict[str, Any] = {
        "_metadata": {
            "slice": SLICE_NAME,
            "split": "second_half_collective_steps",
            "artifacts": str(artifacts),
        },
        "experiments": {},
    }

    for exp_name, required_methods in required.items():
        exp_payload = payload["experiments"].get(exp_name, {"results": {}})
        spec = exp_payload.get("spec")
        if not spec:
            scores["experiments"][exp_name] = {
                "slice": SLICE_NAME,
                "step_split": {"selected_steps": [], "held_out_steps": []},
                "results": {
                    method_name: {
                        **missing_score(),
                        "cct_reduction_vs_strawman_pct": 0.0,
                    }
                    for method_name in required_methods
                },
            }
            continue

        selected = selected_steps(spec)
        all_steps = sorted(int(step["step"]) for step in spec.get("steps", []))
        scores["experiments"][exp_name] = {
            "slice": SLICE_NAME,
            "step_split": {
                "selected_steps": sorted(selected),
                "held_out_steps": [step for step in all_steps if step not in selected],
            },
            "results": score_slice(exp_payload, selected, required_methods),
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(scores, indent=2))
    return scores


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", default="checkpoints")
    parser.add_argument("--output", default="scoring/scores_test.json")
    args = parser.parse_args()
    evaluate(Path(args.artifacts), Path(args.output))


if __name__ == "__main__":
    main()

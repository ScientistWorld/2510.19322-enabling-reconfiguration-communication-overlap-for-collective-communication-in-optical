"""Evaluate scheduler artifacts without importing method code."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_results(artifacts: Path) -> dict:
    merged = {"experiments": {}}
    if not artifacts.exists():
        return merged
    for path in sorted(artifacts.rglob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        for exp_name, exp_payload in payload.get("experiments", {}).items():
            slot = merged["experiments"].setdefault(exp_name, {"results": {}})
            if "spec" in exp_payload:
                slot["spec"] = exp_payload["spec"]
            slot["results"].update(exp_payload.get("results", {}))
    return merged


def evaluate(artifacts: Path, output: Path) -> dict:
    payload = load_results(artifacts)
    scores = {"experiments": {}}
    for exp_name, exp_payload in payload["experiments"].items():
        results = exp_payload["results"]
        spec = exp_payload.get("spec")
        out_results = {}
        strawman_cct = None
        if "strawman_icr" in results:
            strawman_cct = float(results["strawman_icr"]["cct_us"])
        for method_name, result in results.items():
            cct = float(result["cct_us"])
            valid_schedule = float(result.get("valid_schedule", 0.0))
            reconfiguration_events = float(result.get("reconfiguration_events", 0.0))
            step_volume_error_mb = float(result.get("step_volume_error_mb", 0.0))
            max_plane_overlap = float(result.get("max_plane_overlap_us", 0.0))
            if spec and result.get("schedule"):
                diagnostics = schedule_diagnostics(spec, result["schedule"])
                valid_schedule = 1.0 if diagnostics["valid_schedule"] else 0.0
                cct = diagnostics["cct_us"]
                reconfiguration_events = diagnostics["reconfiguration_events"]
                step_volume_error_mb = diagnostics["step_volume_error_mb"]
                max_plane_overlap = diagnostics["max_plane_overlap_us"]
            elif method_name != "strawman_icr":
                valid_schedule = 0.0
            if valid_schedule < 1.0:
                cct = max(cct, 1_000_000_000_000.0)
            row = {
                "cct_us": cct,
                "valid_schedule": valid_schedule,
                "reconfiguration_events": reconfiguration_events,
                "step_volume_error_mb": step_volume_error_mb,
                "max_plane_overlap_us": max_plane_overlap,
            }
            if strawman_cct and method_name != "strawman_icr":
                row["cct_reduction_vs_strawman_pct"] = 100.0 * (strawman_cct - cct) / strawman_cct
            elif method_name == "strawman_icr":
                row["cct_reduction_vs_strawman_pct"] = 0.0
            out_results[method_name] = row
        scores["experiments"][exp_name] = {"results": out_results}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(scores, indent=2))
    return scores


def schedule_diagnostics(spec: dict, schedule: list[dict]) -> dict:
    valid = validate_schedule(spec, schedule)
    by_step = {}
    by_plane = {}
    reconfiguration_events = 0
    for item in schedule:
        by_step.setdefault(int(item["step"]), []).append(item)
        plane = int(item["plane"])
        if int(item.get("reconfigured", 0)):
            reconfiguration_events += 1
            by_plane.setdefault(plane, []).append(
                (float(item["reconfig_start_us"]), float(item["reconfig_end_us"]))
            )
        by_plane.setdefault(plane, []).append(
            (float(item["transmit_start_us"]), float(item["transmit_end_us"]))
        )

    step_volume_error = 0.0
    for step in spec.get("steps", []):
        step_id = int(step["step"])
        observed = sum(float(item["message_mb"]) for item in by_step.get(step_id, []))
        step_volume_error += abs(observed - float(step["message_mb"]))

    cct = max(float(item["transmit_end_us"]) for item in schedule) if schedule else 0.0
    return {
        "valid_schedule": valid,
        "cct_us": cct,
        "reconfiguration_events": float(reconfiguration_events),
        "step_volume_error_mb": step_volume_error,
        "max_plane_overlap_us": max_plane_overlap_us(by_plane),
    }


def max_plane_overlap_us(activities_by_plane: dict[int, list[tuple[float, float]]]) -> float:
    worst = 0.0
    for activities in activities_by_plane.values():
        activities.sort()
        for (_, prev_end), (cur_start, _) in zip(activities, activities[1:]):
            worst = max(worst, max(0.0, prev_end - cur_start))
    return worst


def validate_schedule(spec: dict, schedule: list[dict]) -> bool:
    steps = spec.get("steps", [])
    if not steps or not schedule:
        return False
    tolerance = 1e-4
    by_step = {}
    by_plane = {}
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
            if int(item.get("reconfigured", 0)):
                activities.append((float(item["reconfig_start_us"]), float(item["reconfig_end_us"])))
            activities.append((float(item["transmit_start_us"]), float(item["transmit_end_us"])))
        activities.sort()
        for (_, prev_end), (cur_start, _) in zip(activities, activities[1:]):
            if cur_start + tolerance < prev_end:
                return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", default="checkpoints")
    parser.add_argument("--output", default="scoring/scores.json")
    args = parser.parse_args()
    evaluate(Path(args.artifacts), Path(args.output))


if __name__ == "__main__":
    main()

"""Evaluate scheduler artifacts without importing method code."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_results(paths: list[Path]) -> dict:
    merged = {"experiments": {}}
    for path in paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text())
        for exp_name, exp_payload in payload.get("experiments", {}).items():
            slot = merged["experiments"].setdefault(exp_name, {"results": {}})
            slot["results"].update(exp_payload.get("results", {}))
    return merged


def evaluate(artifacts: Path, output: Path) -> dict:
    payload = load_results(
        [
            artifacts / "baseline" / "baseline_results.json",
            artifacts / "swot" / "swot_results.json",
        ]
    )
    scores = {"experiments": {}}
    for exp_name, exp_payload in payload["experiments"].items():
        results = exp_payload["results"]
        out_results = {}
        strawman_cct = None
        if "strawman_icr" in results:
            strawman_cct = float(results["strawman_icr"]["cct_us"])
        for method_name, result in results.items():
            cct = float(result["cct_us"])
            row = {
                "cct_us": cct,
                "valid_schedule": float(result.get("valid_schedule", 0.0)),
                "reconfiguration_events": float(result.get("reconfiguration_events", 0.0)),
            }
            if strawman_cct and method_name == "swot":
                row["cct_reduction_vs_strawman_pct"] = 100.0 * (strawman_cct - cct) / strawman_cct
            elif method_name == "strawman_icr":
                row["cct_reduction_vs_strawman_pct"] = 0.0
            out_results[method_name] = row
        scores["experiments"][exp_name] = {"results": out_results}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(scores, indent=2))
    return scores


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", default="checkpoints")
    parser.add_argument("--output", default="scoring/scores.json")
    args = parser.parse_args()
    evaluate(Path(args.artifacts), Path(args.output))


if __name__ == "__main__":
    main()

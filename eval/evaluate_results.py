"""Visible evaluation: train families plus the paper's own named instances.

Writes ``scoring/scores_train.json`` (the train slice of the scored
experiments) and ``scoring/scores.json`` (the same train experiments plus one
unscored ``_paper_*`` experiment per paper instance: Fig. 5 8-node example and the Fig. 8
64/512-node AllReduce points). Solvers are run through the same interface as
the hidden test (``scripts/solvers/<method>.sh``); this module never imports
method code and recomputes every number from the serialized schedules.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.train import evaluate as train_eval

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PAPER_INSTANCES = HERE / "paper_instances.json"


def evaluate(output: Path, train_output: Path) -> dict:
    train_scores = train_eval.evaluate(train_output)
    scores = {
        "_metadata": {
            "slice": "visible (train families + paper instances)",
            "note": "Paper-instance experiments are unscored reproduction checks of the paper's named settings.",
            **{key: value for key, value in train_scores["_metadata"].items() if key != "slice"},
        },
        "experiments": dict(train_scores["experiments"]),
    }
    paper = json.loads(PAPER_INSTANCES.read_text())["instances"]
    methods = train_eval.discover_methods()
    for name, instance in paper.items():
        strawman = train_eval.strawman_cct_us(instance)
        results = {
            train_eval.BASELINE_METHOD: {
                "cct_us": strawman,
                train_eval.PRIMARY: 0.0,
                "valid_schedule": 1.0,
            }
        }
        status = {}
        for method in methods:
            outcome = train_eval.evaluate_method(method, {name: [instance]})
            if outcome["failure"] is not None:
                results[method] = {"cct_us": 2.0 * strawman, **train_eval.WORST_ROW}
            else:
                detail = outcome["details"][instance["id"]]
                results[method] = {
                    "cct_us": detail["cct_us"],
                    train_eval.PRIMARY: detail[train_eval.PRIMARY],
                    "valid_schedule": 1.0,
                }
            status[method] = {"run_failed": outcome["failure"] is not None, "failure": outcome["failure"]}
        scores["experiments"][f"_{name}"] = {"results": results, "_status": status, "_unscored": True}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(scores, indent=2))
    return scores


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "scoring" / "scores.json"))
    parser.add_argument("--train-output", default=str(ROOT / "scoring" / "scores_train.json"))
    args = parser.parse_args()
    evaluate(Path(args.output), Path(args.train_output))


if __name__ == "__main__":
    main()

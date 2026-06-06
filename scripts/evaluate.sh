#!/bin/bash
# Evaluation script — the standard way to evaluate work in this environment.
#
# This script must be SELF-CONTAINED using only code in eval/.
# Do NOT import from method/ — evaluate.sh must work even when the
# paper's method code is hidden from a scientist agent.
#
# Design it so that anyone following the same output format can run
# this script to evaluate their results.
#
# OUTPUT CONTRACT: This script writes scoring/scores.json in the benchmark
# structure:
#   {"experiments": {"experiment_name": {"results": {"method": {"metric": value}}}}}
# Experiment, method, and metric names should match scoring/reference.json
# when reproducing a paper-reported target.
#
# Example usage:
#   bash scripts/evaluate.sh
#
# Called from run.sh after training, or independently.

set -e

cd /home/user

mkdir -p scoring

python -m eval.evaluate_results --artifacts checkpoints --output scoring/scores.json

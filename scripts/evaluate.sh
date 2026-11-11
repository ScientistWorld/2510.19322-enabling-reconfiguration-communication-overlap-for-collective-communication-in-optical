#!/bin/bash
# Visible evaluation — the standard way to evaluate work in this environment.
#
# Uses only code in eval/ (never method/). Runs every solver registered in
# scripts/solvers/<method>.sh on the visible train instances and on the
# paper's three named instances, then writes
#   scoring/scores_train.json  (the scored experiments, train slice)
#   scoring/scores.json        (the same experiments + unscored paper-instance checks)
# in the benchmark structure
#   {"experiments": {"experiment_name": {"results": {"method": {"metric": value}}}}}

set -euo pipefail

cd /home/user

mkdir -p scoring

python -m eval.evaluate_results --output scoring/scores.json --train-output scoring/scores_train.json

#!/bin/bash
# Reproduce the paper's results end-to-end (visible side).
#
# Writes the Strawman-ICR schedules, then runs the SWOT MILP on every visible
# instance through scripts/solvers/swot.sh and scores them
# (scoring/scores.json, scoring/scores_train.json). The held-out test is
# scored separately by scripts/evaluate_test.sh.

set -euo pipefail

cd /home/user

rm -rf checkpoints/baseline checkpoints/swot checkpoints/train

bash scripts/baseline.sh
bash scripts/method.sh

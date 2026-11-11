#!/bin/bash
# Score every method on disk on the held-out test instances.
#
# Runs each scripts/solvers/<method>.sh (plus the required `swot`) on every
# instance in eval/test/ under the fixed time limit, validates each schedule
# against the frozen instance and the physical model, and writes
# scoring/scores_test.json:
#   {"experiments": {"experiment_name": {"results": {"method": {"metric": value}}}}}
# Takes no arguments. Never imports method code.

set -euo pipefail

cd /home/user

mkdir -p scoring

python -m eval.test.evaluate --output scoring/scores_test.json

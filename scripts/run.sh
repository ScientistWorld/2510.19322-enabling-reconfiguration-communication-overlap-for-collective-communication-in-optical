#!/bin/bash
# Hardening exploration job (iteration 12, step 1 of 2):
#   1. calibrate the reference's deterministic CBC node budget (method/budget.json);
#   2. smoke-test the reference, the positive control and the relay rule;
#   3. run reference / relay rule / positive control / 30 s annealing / reference seed 2
#      on the exploration instances (hardening/explore/instances.json) -> results.jsonl.
# The final scripts/run.sh reproduces the reference end to end.

set -euo pipefail

cd /home/user

python -c "import pulp, sys, os; print('python', sys.version.split()[0], 'pulp', pulp.__version__, 'cpus', len(os.sched_getaffinity(0)))"
python -m hardening.calibrate
python -c "from hardening import harness; import sys; sys.exit(0 if harness.smoke() else 2)"
python -m hardening.explore

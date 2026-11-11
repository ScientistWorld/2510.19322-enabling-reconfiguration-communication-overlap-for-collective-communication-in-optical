#!/bin/bash
# Hardening verification job (iteration 11). Runs inside the compute container
# with the workspace at /home/user and no internet.
#
# 1. smoke-tests both MILP solvers, then runs the reference, the stronger and
#    weaker variants and every shortcut probe through the real evaluators
#    (hardening/harness.py; resumable), leaving the reference scores in
#    scoring/scores_test.json, scoring/scores_train.json and scoring/scores.json;
# 2. writes the paper-instance inspection artifacts and validates the workspace.

set -euo pipefail

cd /home/user

python -c "import pulp, sys; print('python', sys.version.split()[0], 'pulp', pulp.__version__)"
python -m hardening.harness all
bash scripts/baseline.sh
python validate.py --compare

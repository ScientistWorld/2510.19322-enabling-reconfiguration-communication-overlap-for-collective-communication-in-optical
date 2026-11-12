#!/bin/bash
# Reproduce the reference end to end inside the compute container
# (workspace at /home/user, no internet, 1 CPU is enough).
#
# 1. scripts/reproduce.sh: Strawman-ICR schedules for the paper instances, then
#    the SWOT MILP (scripts/solvers/swot.sh, 120 s per instance) on every
#    visible instance -> scoring/scores_train.json and scoring/scores.json
#    (~45 min);
# 2. scripts/evaluate_test.sh: the same solver on the held-out instances ->
#    scoring/scores_test.json (~35 min);
# 3. workspace validation.
#
# The iteration-11 hardening check (variants and shortcut probes) is
# `python -m hardening.harness all`; its results are in hardening/runs/.

set -euo pipefail

cd /home/user

python -c "import pulp, sys; print('python', sys.version.split()[0], 'pulp', pulp.__version__)"
bash scripts/reproduce.sh
bash scripts/evaluate_test.sh
python validate.py --compare

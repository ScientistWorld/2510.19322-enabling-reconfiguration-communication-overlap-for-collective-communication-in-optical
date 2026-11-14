#!/bin/bash
# Reproduce the reference end to end inside the compute container
# (workspace at /home/user, no internet, 1 CPU is enough).
#
# 1. scripts/reproduce.sh: Strawman-ICR schedules for the paper instances, then
#    the SWOT MILP (scripts/solvers/swot.sh: CBC with the deterministic node
#    budget in method/budget.json and no time limit) on every visible instance
#    -> scoring/scores_train.json and scoring/scores.json (~25 min);
# 2. scripts/evaluate_test.sh: the same solver on the held-out instances ->
#    scoring/scores_test.json (~25 min);
# 3. workspace validation.
#
# The iteration-13 hardening check (a second reference run, variants and
# shortcut probes, ~2 h on 4 CPUs) is `python -m hardening.harness all`; its
# results are in hardening/final_runs/ and hardening/results.md.

set -euo pipefail

cd /home/user

python -c "import pulp, sys; print('python', sys.version.split()[0], 'pulp', pulp.__version__)"
bash scripts/reproduce.sh
bash scripts/evaluate_test.sh
python validate.py --compare

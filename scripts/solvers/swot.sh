#!/bin/bash
# Solver interface for the method scored as `swot`.
#
# Every evaluator (visible train, hidden test, paper instances) calls
#   bash scripts/solvers/<method>.sh INSTANCE_JSON OUTPUT_JSON CPU_BUDGET_S
# from the workspace root, once per workload instance. CPU_BUDGET_S (120) is
# counted by the evaluator over every process the solver starts; more fails
# the run. The solver must write {"schedule": [...]} to OUTPUT_JSON and exit 0.
# See briefing/evaluation.md.
#
# This one runs the paper's SWOT MILP (CBC via PuLP) with the deterministic
# node budget in method/budget.json.

set -euo pipefail
cd /home/user
exec python -m method.swot_scheduler --instance "$1" --output "$2" --time-limit-s "$3"

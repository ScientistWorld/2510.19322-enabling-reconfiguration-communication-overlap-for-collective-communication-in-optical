#!/bin/bash
# Solver interface for the method scored as `swot`.
#
# Every evaluator (visible train, hidden test, paper instances) calls
#   bash scripts/solvers/<method>.sh INSTANCE_JSON OUTPUT_JSON TIME_LIMIT_S
# from the workspace root, once per workload instance, and kills the process
# group TIME_LIMIT_S + 30 seconds after it starts. The solver must write
# {"schedule": [...]} to OUTPUT_JSON and exit 0. See briefing/evaluation.md.
#
# This one runs the paper's SWOT MILP (CBC via PuLP, 120 s limit).

set -euo pipefail
cd /home/user
exec python -m method.swot_scheduler --instance "$1" --output "$2" --time-limit-s "$3"

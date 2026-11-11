#!/bin/bash
# Run the paper's proposed method (SWOT MILP) through the solver interface.
#
# The method is exposed to every evaluator as scripts/solvers/swot.sh; this
# script runs it on all visible instances (train families + paper examples)
# via scripts/evaluate.sh. Schedules are kept under checkpoints/train/swot/.
#
# Usage:
#   bash scripts/method.sh

set -euo pipefail

cd /home/user

bash scripts/evaluate.sh

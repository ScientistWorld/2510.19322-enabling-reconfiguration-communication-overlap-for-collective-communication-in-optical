#!/bin/bash
# Run the paper's proposed method.
#
# This script trains/runs the paper's method using code in method/.
#
# Usage:
#   bash scripts/method.sh

set -e

cd /home/user

python -m method.swot_scheduler --output-dir checkpoints/swot --time-limit-s "${SWOT_SOLVER_TIME_LIMIT:-120}"
bash scripts/evaluate.sh

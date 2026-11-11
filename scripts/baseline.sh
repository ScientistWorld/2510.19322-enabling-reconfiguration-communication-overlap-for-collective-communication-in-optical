#!/bin/bash
# Paper baseline (Strawman-ICR, lockstep intra-collective reconfiguration).
#
# The evaluators compute this baseline themselves from each frozen instance;
# this script only writes its explicit schedules for the paper's named
# instances to checkpoints/baseline/ for inspection.
#
# Usage:
#   bash scripts/baseline.sh

set -euo pipefail

cd /home/user

python -m baseline.simulate_baselines --output-dir checkpoints/baseline

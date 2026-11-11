#!/bin/bash
# Score every method on disk on the visible train instances (eval/train/).
#
# Same interface, time limit, validation and metrics as the hidden test.
# Writes scoring/scores_train.json:
#   {"experiments": {"experiment_name": {"results": {"method": {"metric": value}}}}}
# Each method's train schedules are kept under checkpoints/train/<method>/.

set -euo pipefail

cd /home/user

mkdir -p scoring

python -m eval.train.evaluate --output scoring/scores_train.json

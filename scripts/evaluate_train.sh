#!/bin/bash
# Evaluate the visible train slice without importing method code.
#
# OUTPUT CONTRACT: writes scoring/scores_train.json in the benchmark structure:
#   {"experiments": {"experiment_name": {"results": {"method": {"metric": value}}}}}

set -e

cd /home/user

mkdir -p scoring

python -m eval.train.evaluate --artifacts checkpoints --output scoring/scores_train.json

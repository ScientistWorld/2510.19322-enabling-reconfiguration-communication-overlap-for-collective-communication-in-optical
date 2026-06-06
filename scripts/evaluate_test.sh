#!/bin/bash
# Evaluate the held-out test slice without importing method code.
#
# OUTPUT CONTRACT: writes scoring/scores_test.json in the benchmark structure:
#   {"experiments": {"experiment_name": {"results": {"method": {"metric": value}}}}}
#
# The test slice scores every method entry present in scoring/scores_train.json.

set -e

cd /home/user

mkdir -p scoring

python -m eval.test.evaluate \
  --artifacts checkpoints \
  --train-scores scoring/scores_train.json \
  --output scoring/scores_test.json

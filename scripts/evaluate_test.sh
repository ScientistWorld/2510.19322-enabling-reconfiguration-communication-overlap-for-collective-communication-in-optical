#!/bin/bash
# Evaluate the held-out test slice without importing method code.
#
# OUTPUT CONTRACT: writes scoring/scores_test.json in the benchmark structure:
#   {"experiments": {"experiment_name": {"results": {"method": {"metric": value}}}}}

set -e

cd /home/user

mkdir -p scoring

python -m eval.test.evaluate \
  --artifacts checkpoints \
  --output scoring/scores_test.json

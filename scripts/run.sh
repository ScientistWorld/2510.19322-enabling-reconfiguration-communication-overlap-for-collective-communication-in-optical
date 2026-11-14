#!/bin/bash
# Hardening follow-up (iteration 12): rerun the full-budget annealing probe
# (its first run hit the old per-process CPU backstop) through the isolated
# harness, then re-publish the reference score files and re-analyze.
# After this job scripts/run.sh is restored to the plain end-to-end reproduction.

set -euo pipefail

cd /home/user

python -c "import pulp, sys; print('python', sys.version.split()[0], 'pulp', pulp.__version__)"
python -m hardening.harness shortcut_private_search
python validate.py --compare || true

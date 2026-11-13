#!/bin/bash
# Hardening job (iteration 12, step 2 of 2): every reference, variant and
# shortcut run through the unmodified scripts/evaluate_test.sh (and the visible
# evaluators), resumable; writes hardening/runs/, hardening/results.md and the
# reference score files. The node budget in method/budget.json was calibrated
# in step 1. After this job scripts/run.sh is restored to the plain
# end-to-end reproduction.

set -euo pipefail

cd /home/user

python -c "import pulp, sys; print('python', sys.version.split()[0], 'pulp', pulp.__version__)"
python -m hardening.harness all
python validate.py --compare || true

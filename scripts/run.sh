#!/bin/bash
# TEMPORARY (iteration-13 hardening, job 1): smoke/determinism check, then the
# corrected reference (no wall-clock limit) against variants on the candidate
# families, one solver process at a time. Restored to the end-to-end
# reproduction afterwards.

set -euo pipefail

cd /home/user

python -c "import pulp, sys; print('python', sys.version.split()[0], 'pulp', pulp.__version__)"
python -m hardening.iter13 explore

#!/bin/bash
# Iteration-13 final job: reproduce the reference end to end (alone), then the
# hardening check, then validate. Completion markers (gitignored) let a
# preempted job skip finished steps. The plain end-to-end reproduction is
# steps 1, 2 and 4.
#
# 1. scripts/reproduce.sh: Strawman-ICR schedules for the paper instances, then
#    the SWOT MILP (scripts/solvers/swot.sh: CBC with the deterministic node
#    budget in method/budget.json, no time limit) on every visible instance ->
#    scoring/scores_train.json and scoring/scores.json;
# 2. scripts/evaluate_test.sh: the same solver on the held-out instances ->
#    scoring/scores_test.json;
# 3. python -m hardening.harness all: a second, independent reference run
#    (must reproduce step 2 exactly), then variants and shortcut probes through
#    the hidden-test evaluator -> hardening/final_runs/, hardening/results.md;
# 4. workspace validation.

set -euo pipefail

cd /home/user

MARK=hardening/_runtime_iter13/markers
mkdir -p "$MARK"
python -c "import pulp, sys; print('python', sys.version.split()[0], 'pulp', pulp.__version__)"
if [ ! -f "$MARK/reproduce.done" ]; then
    bash scripts/reproduce.sh
    touch "$MARK/reproduce.done"
fi
if [ ! -f "$MARK/evaluate_test.done" ]; then
    bash scripts/evaluate_test.sh
    touch "$MARK/evaluate_test.done"
fi
python -m hardening.harness all
python validate.py --compare

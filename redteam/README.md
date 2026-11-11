# Scoring audit runs

Each candidate has `redteam/<name>/run.sh`. It installs the candidate in
`method/audit_candidate.py`, produces checkpoint artifacts using agent-visible
inputs, runs the original `bash scripts/evaluate_test.sh` with no arguments in a
fresh process, and preserves the emitted scores in that candidate's folder.
The orchestrator restores checkpoints, scoring files and the temporary method
file after each run. It does not modify evaluation code, imports, or environment.

Run the full bundle with `bash redteam/run_all.sh` on a CPU compute node.
The completed default reference precedes shortcuts, which reuse its freshly
regenerated outputs; seed reruns and the stronger solve follow. Completed trials
are reused when resuming. No shortcut reads initial test scores,
the paper, or hidden evaluation code to construct its answers.

`analyze.py` uses the audit's initial test reference and rubric solely to report
results. Ranks depend on the other attempts used for normalization; it reports
explicit audit populations rather than inventing a platform-wide score.
Zero is the reference rank in all populations. Raw scores are authoritative.

`initial_state/starting_status.txt` records pre-existing changes to README.md,
manifest.json and trajectory files, which this audit does not touch. README.md
and manifest.json were already character devices at the start of this audit.

For quality comparisons use the fixed six-attempt cohort: initial reference,
three explicit reference seeds, stronger solver, weaker lockstep. For shortcuts
use that cohort plus the candidate, so newly varying correctness metrics receive
their penalty. Fixed-quality ranks for shortcuts remain in summary.json for
transparency but are not suitable for assessing shortcuts whose failure varies
a metric that was constant across the honest population.

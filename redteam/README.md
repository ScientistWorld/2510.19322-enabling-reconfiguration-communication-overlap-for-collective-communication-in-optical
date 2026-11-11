# Scoring audit runs

Each candidate has `redteam/<name>/run.sh`. It installs the candidate in
`method/audit_candidate.py`, produces checkpoint artifacts using agent-visible
inputs, runs the original `bash scripts/evaluate_test.sh` with no arguments in a
fresh process, and preserves the emitted scores in that candidate's folder.
The orchestrator restores checkpoints, scoring files and the temporary method
file after each run. It does not modify evaluation code, imports, or environment.

Run the full bundle with `bash redteam/run_all.sh` on a CPU compute node.
Solver runs precede shortcuts so the shortcuts may reuse freshly regenerated
outputs of the visible reference method. No shortcut reads initial test scores,
the paper, or hidden evaluation code to construct its answers.

`analyze.py` uses the audit's initial test reference and rubric solely to report
results. Ranks depend on the other attempts used for normalization; it reports
three explicit audit populations rather than inventing a platform-wide score.
Zero is the reference rank in all populations. Raw scores are authoritative.

`initial_state/starting_status.txt` records pre-existing changes to README.md,
manifest.json and trajectory files, which this audit does not touch. README.md
and manifest.json were already character devices at the start of this audit.

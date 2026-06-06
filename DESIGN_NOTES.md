# Train/Test Evaluation Design Notes

Checked the existing split, both evaluator wrappers, the slice evaluators, artifact loading, metric definitions, and train/test leakage patterns. The design was already artifact-based and did not import `method/`, which is the right interface for improve-mode and from-scratch submissions.

Changes made:
- Added constraint-side diagnostics to both slices: `reconfiguration_events`, `step_volume_error_mb`, and `max_plane_overlap_us`, in addition to CCT, CCT reduction, and schedule validity. These make it harder to game visible CCT by emitting impossible schedules with missing volume or overlapping plane activities.
- Made `eval/test/evaluate.py` enumerate method entries directly from serialized artifacts instead of depending on `scoring/scores_train.json`. This keeps held-out scoring self-contained and avoids a failure mode where final test scoring silently requires a prior visible-train run.
- Added required `description` fields for all active metrics in `scoring/reference.json` and registered the new metrics in each existing experiment. No paper-agreement metrics were added.
- Kept the split style as first-half collective steps for train and second-half collective steps for test because the paper's method is a scheduler and this split probes whether improvements generalize across the reduce-scatter/allgather timeline while reusing the same serialized method artifacts.

Static checks completed:
- `bash -n scripts/evaluate_train.sh`
- `bash -n scripts/evaluate_test.sh`
- `scoring/reference.json` parses as JSON.
- No `scoring/scores_train.json` or `scoring/scores_test.json` stubs exist.
- Grep found no cross-imports between `eval/train/` and `eval/test/`.

Runtime concerns for the runner iteration:
- The step split is deterministic and small for the 8-node Fig. 5 example, so train/test gap signal there may be coarse. The two larger Fig. 8 workloads should carry most of the anti-shortcut signal.
- The evaluators expect future methods to serialize schedules with the same field names used by the current artifacts: `step`, `config`, `plane`, `message_mb`, reconfiguration times, and transmission times. A method that only writes aggregate CCT can still be scored, but it will receive large penalties on the newly added schedule-feasibility diagnostics unless it emits schedule-level artifacts.
- The added overlap and volume-error metrics should be checked once by the runner on actual generated artifacts to confirm they are zero for valid schedules and nonzero for malformed schedules.

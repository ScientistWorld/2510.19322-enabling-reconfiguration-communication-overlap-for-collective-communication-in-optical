# Train/Test Evaluation Design Notes

Current design (iteration 11 hardening; see `HARDENING.md` for evidence):

- Methods are solvers: `scripts/solvers/<method>.sh INSTANCE OUTPUT TIME_LIMIT` (scored key `swot`). The evaluators run every solver on disk once per instance, with the paper's 120 s limit and a 150 s kill.
- Train (`eval/train/`, public instances) and test (`eval/test/`, held-out instances) are independent copies of the same evaluator. They share no code and never import `method/`. Instances come from the same three families and ranges, 6 per family each.
- Every number is recomputed from the serialized schedule against the evaluator's frozen instance: full physical validation, full-collective CCT from time 0, and the Strawman-ICR baseline computed by the evaluator.
- Any failed instance fails the whole run, which gets worst values in every metric of every experiment.
- `scripts/evaluate.sh` writes `scores_train.json` plus `scores.json`. `scores.json` adds unscored `_paper_*` checks on the paper's Fig. 5 / Fig. 8 instances.

Superseded: the earlier design scored a step-suffix slice of three public instances from method-written artifacts under `checkpoints/`.

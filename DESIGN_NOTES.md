# Train/Test Evaluation Design Notes

Current design (iteration 13 hardening; see `HARDENING.md` for evidence):

- Methods are solvers: `scripts/solvers/<method>.sh INSTANCE OUTPUT CPU_BUDGET_S` (scored key `swot`). The evaluators run every solver on disk once per instance. The budget is 120 CPU-seconds per instance, counted by the evaluator over the solver's whole process tree (subreaper; detached processes are reaped and counted). There is a 135 CPU-s per-process backstop and a 300 s wall-clock cap for hung solvers.
- Train (`eval/train/`, public) and test (`eval/test/`, held out) are independent copies of the same evaluator and of the instance generator (`make_instances.py`, different seeds; the test seed exists only in `eval/test/`). They share no code and never import `method/`. There are 10/12/12 instances per family, stratified over each family's switching-share band, with no duplicates.
- Families: `allreduce_scaling` (Fig. 8a, k=4), `high_optical_degree` (Fig. 7a ReduceScatter, k=8), `hardware_sensitivity` (Section 4.3 sweep over k and T_recfg). Settings where a 15-line relay rule matches the paper's budget-limited MILP are not scored: AllReduce, Bruck and Pairwise at k=8, Bruck and Pairwise at k=4 (Pairwise's k=4 cell of the hardware grid holds ReduceScatter since iteration 13), and collectives beyond 1024 nodes (measured in iteration 13: the reference stays at or near the lockstep baseline there and the relay rule beats it).
- Every number is recomputed from the serialized schedule against the evaluator's frozen instance: full physical validation, full-collective CCT from time 0, and the Strawman-ICR baseline computed by the evaluator. Any failed or over-budget instance fails the whole run, which gets the worst value in every metric of every experiment.
- The reference solver is deterministic: CBC with a calibrated node budget (`method/budget.json`), no time limit of any kind (CBC in CPU-time mode, a CPU-time kill switch outside CBC as the only safety stop), PuLP pinned to 3.3.2.
- Before any solver runs, the evaluators write their output file with every method failed; it is replaced atomically when all methods are scored.
- `scripts/evaluate.sh` writes `scores_train.json` plus `scores.json`. `scores.json` adds unscored `_paper_*` checks on the paper's Fig. 5 / Fig. 8 instances.

Superseded: iteration 12 still passed CBC a wall-clock `sec` safety limit; iteration 11 used a 120 s wall-clock limit (time-limited CBC) and 6 instances per family; before that, a step-suffix slice of three public instances scored from method-written artifacts.

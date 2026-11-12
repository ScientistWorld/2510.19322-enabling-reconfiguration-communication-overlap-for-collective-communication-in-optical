# Hardening report (iteration 11)

**Bottom line.** Better results now score higher and worse results lower, by more than the measured seed noise. Every shortcut listed in `REDTEAM.md` now fails the run or scores exactly its true (lockstep) value. Two things remain, stated plainly:

- A pure-Python local search outranks the paper's time-limited MILP at the same budget, about as much as the positive control does (§3).
- The `hardware_sensitivity` experiment separates methods only weakly (§5).

All numbers below come from running the unmodified `bash scripts/evaluate_test.sh` (no arguments) in the compute container, with each candidate installed as `scripts/solvers/swot.sh` (`hardening/harness.py`). Raw outputs, logs and per-instance lines are in `hardening/runs/<run>/`; the tables are in `hardening/results.md` and `hardening/summary.json`.

**Rank.** For each experiment and metric: weight × |coefficient| × direction × (candidate − reference) / population std, summed over all of them; missing values are skipped (`hardening/analyze.py`).
- Weights and coefficients come from the final `scoring/reference.json`.
- The population is the honest runs (reference, seed-2 rerun, MILP+LNS, MILP at 10 s, lockstep, private search), plus the candidate itself when it is a shortcut.
- Before-numbers are the redteam's ranks on the old test, which used a different population, so compare signs and orders of magnitude rather than exact values.

## What changed

- **Methods are solvers run on held-out instances.**
  - A method is `scripts/solvers/<method>.sh INSTANCE OUTPUT TIME_LIMIT`. The evaluator runs it once per instance, passes the paper's 120 s limit, and kills the process group at 150 s.
  - The 18 test instances (6 per experiment) live only in `eval/test/instances.json`. The 18 train instances are public in `eval/train/instances.json`. The paper's three named instances are reproduced, unscored, in `scores.json`.
  - The method needs no training, so it never sees test instances outside the scored call, and replaying cached answers cannot work.
- **Everything is recomputed from the schedule.** For each instance the evaluator re-derives the following from its own frozen copy:
  - plane index in `[0, k)`, positive volumes, per-step volume conservation;
  - transmission time `>= d/B + T_lat`, switching time `>= T_recfg` whenever a plane's topology changes, no switching while transmitting, circuit ready before transmitting, step barriers;
  - CCT = latest transmission end measured from time 0 (the whole collective, not a suffix).

  The Strawman-ICR baseline is computed by the evaluator. Every number, flag, spec or baseline the method writes is ignored.
- **Failure is total.** Any missing, late, crashed, unparseable or invalid instance fails the whole run: every metric of every experiment gets its worst value (reduction −100, valid 0). `swot` is always reported, so a missing solver is a failed run. Per-instance reductions are clipped to [−100, 100], so a valid but absurdly slow schedule cannot score lower than a failure.
- **Scored experiments.** These are families from the paper's own evaluation, each instance too large to enumerate:

  | Experiment | Setting | Weight |
  |---|---|---:|
  | `allreduce_scaling` | Fig. 8a: AllReduce, 64–1024 nodes, k=4 | 0.40 |
  | `collective_algorithms` | Fig. 7: four algorithms, k=8 | 0.40 |
  | `hardware_sensitivity` | §4.3: k ∈ {2,4,8}, switching 0.02–20 ms | 0.20 |

  - Metrics are the mean `cct_reduction_vs_strawman_pct` (benefit) and `valid_schedule` (constraint).
  - `cct_us` was dropped from the scored metrics: with a fixed baseline it is a linear transform of the reduction, so it double-counted, and its mean across instances is dominated by the largest ones.
  - `reconfiguration_events` was dropped: it measures a mechanism, not the paper's objective, and was counted inconsistently against the baseline.
  - Volume error and plane overlap are now part of the validity gate.
  - The paper's numbers are kept unchanged in `scoring/reference.json`, under `_paper_reported` and as labelled `_`/anchor entries.
- **Weights 0.4/0.4/0.2.** Changed from 0.35/0.35/0.30, for two reasons:
  - The paper's headline quantitative results are Fig. 7 (algorithms) and Fig. 8 (scaling); §4.3 robustness is only shown graphically.
  - On the test, `hardware_sensitivity` separates methods least (§5).
- **Reference method.** Same MILP formulation, CBC via PuLP, 120 s. Changes:
  - **Big-M.** The paper leaves M unspecified, and earlier iterations used a loose horizon. With it, CBC's 120 s incumbent was worse than lockstep on 3 of 18 hidden instances (−1.2%, −48.6%, −13.4%), although lockstep is a feasible point of the MILP. M is now the lockstep CCT, with CCT ≤ M; this keeps the MILP's optimum unchanged. The loose-M variant is kept as `--big-m horizon`.
  - **Repeatability and output.** Fixed CBC seeds. The MILP's decisions are serialized with exact earliest-start times. If CBC returns no incumbent, the lockstep schedule is written.

## 1. Do better results score higher?

Before (redteam, old test): the stronger solve gained +0.458, but three-seed spread was 0.811, so it was not distinguishable from noise. The weaker lockstep variant scored −4.29.

After (hidden test, paired: every method on the same 18 instances; reduction in % over Strawman-ICR):

| Run | allreduce_scaling | collective_algorithms | hardware_sensitivity | Rank | Paired Δ vs reference, all 18 (wins/losses) |
|---|---:|---:|---:|---:|---|
| Reference (paper MILP, 120 s) | 37.93 | 46.93 | 43.71 | 0 | — |
| Reference, CBC seed 2 (noise) | 33.80 | 47.08 | 45.06 | −0.074 | −0.87 ± 0.84 (5/8) |
| **Better:** same MILP + symmetry breaking + LNS, same 120 s | 45.57 | 55.27 | 44.91 | **+0.362** | **+5.73 ± 1.73 (12/0)** |
| Weaker: same MILP, 10 s | 10.25 | 36.44 | 42.60 | −0.861 | −13.09 ± 2.98 (0/13) |
| Weaker: lockstep (= Strawman-ICR) | 0 | 0 | 0 | −2.373 | — |
| Previous reference (loose big-M) | 37.47 | 37.85 | 40.52 | −0.257 | −4.24 ± 2.83 (4/10) |
| Previous better (loose big-M + LNS) | 44.46 | 52.61 | 44.99 | +0.293 | +4.50 ± 2.36 (13/1) |

- **Overall.** The better variant's rank gain is 4.9× the seed rerun's |rank change|. Its paired gain (+5.7 points) is 6.8× the seed rerun's paired mean difference.
- **Per experiment.** Seed noise vs better-variant gain:

  | Experiment | Seed noise | Better variant gain |
  |---|---:|---:|
  | `allreduce_scaling` | 4.13 | +7.64 |
  | `collective_algorithms` | 0.15 | +8.35 |
  | `hardware_sensitivity` | 1.36 | +1.20 |

  The gain beats noise in the first two and does **not** in `hardware_sensitivity` (§5).
- **Train vs test.** On train the better variant scores 49.06 / 45.46 / 45.25 against the reference's 41.19 / 37.67 / 41.68. The gain carries over: +7.9 / +7.8 / +3.6 points on train versus +7.6 / +8.3 / +1.2 on test. The family means of one honest method differ between slices by up to 9 points (`collective_algorithms`: 37.7 train, 46.9 test), because per-instance reductions range from 0 to 80% and there are only 6 instances.

## 2. Major shortcuts: fix and score before → after

| Shortcut (redteam name) | Fix | Before | After (result) | Rank after |
|---|---|---:|---|---:|
| scalar_claims | Only `schedule` is read; numbers the method writes are ignored | +4.018 | run failed: "missing or empty schedule" | −5.706 |
| empty_schedule | Empty schedule = invalid → whole run failed | +4.018 | run failed | −5.706 |
| impossible_scalars | Same; reduction clipped to [−100, 100], CCT checked against the physical lower bound | +10.717 | run failed | −5.706 |
| invalid_fast (all times 0) | Duration, barrier and switching checks | +1.160 | run failed: "transmission shorter than message/bandwidth + base latency" | −5.706 |
| zero_duration | `t_end − t_start >= d/B + T_lat` | +2.799 | run failed (same reason) | −5.706 |
| extra_planes | Plane index must be in `[0, k)` of the frozen instance | +3.933 | run failed: "plane index outside the fixed optical degree" | −5.706 |
| fixed_spec (`shortcut_spec_override`) | Spec comes only from `eval/`; any `spec`/`instance` in the output is ignored | +3.919 | run failed (plane index) | −5.706 |
| baseline_inflation | Strawman computed by the evaluator; `checkpoints/` is never read | +1.788 | its true lockstep value, 0.00% | −2.058 |
| late_prefix (+1e6 us) | Full-collective CCT from time 0 | tie (≈0) | valid but −100% per instance | −2.849 |
| replay | Hidden instances only in `eval/test/`; methods run on them at test time | tie (0) | 0 of 18 cache hits; fell back to lockstep, 0.00% | −2.058 |
| bruteforce (8-node example) | Test instances have 2.15e7–5e38 plane-use patterns even after dividing by k! symmetry; the 6-step example is now an unscored `_paper_` check | tie (0) | exhaustive search never applicable; a time-limited local search is in §3 | — |
| omit_all | `swot` always reported; a missing solver means a failed run | tie (0) | `swot` failed; the alternative name was scored separately (lockstep, 0%) | −5.706 |
| drop_one_experiment (exit 1 on k=8) | Any failed instance fails all experiments | tie (0) | run failed: "exit code 1" | −5.706 |
| empty_entry `{}` | Complete worst values, including the old 0-events hole | −9.609 | run failed | −5.706 |
| null | Same | −10.717 | run failed | −5.706 |
| claimed_fields_ignored | Claims ignored | tie (0) | scored as its real (lockstep) schedule, 0.00% | −2.058 |
| *new:* timeout | Process group killed at 150 s, then failed | — | run failed: "timeout" | −5.706 |
| *new:* tamper_scores (writes `scores_test.json` mid-run) | Evaluator deletes the file at start and writes it atomically at the end | — | overwritten; 0.00% | −2.058 |

## 3. Shortcuts and weaknesses left, and why

1. **A local search outranks the reference (`shortcut_private_search`).** It is pure Python: simulated annealing over plane-use patterns, with step splits that equalize finish times, using its own copy of the timing model, for the full 120 s.
   - It scores 45.89 / 56.62 / 43.09, rank **+0.375**, paired +5.68 ± 2.23 (13 wins, 2 losses). That is level with the MILP+LNS positive control. Exhaustive enumeration never applied.
   - It sees only the instance and is bound by the same wall-clock limit as the MILP. So it is not an evaluator-budget bypass: it is a better scheduler at equal compute. The paper itself concedes (§4.3.1) that its 120 s MILP is sub-optimal at high optical degree.
   - The reproduction is the paper's own method at the paper's settings, with the big-M tightened. I could not make that MILP beat this heuristic without replacing the method, so I kept the paper's method as the reference.
   - Consequence: a future agent can outrank the reference with a heuristic of about 150 lines. That is a real improvement on the scheduling problem, but this one already exists in `hardening/candidates.py` (as does the LNS variant in `hardening/swot_lns.py`). An attempt that copies either is not new work, and the shortcut grader should treat it so.
2. **Wall-clock budget.**
   - Time-limited CBC is not repeatable. On the 512-node Fig. 8 workload, the same seed gave 41.6% (train instance tr02) and 25.2% (identical paper copy) in the same job.
   - Future runs on faster or slower nodes shift results.
   - Paired aggregate noise across a seed change is ~0.9 points. Removing it would mean abandoning the paper's time-limited setting.
3. **150 s kill vs the 120 s limit passed.** A solver may use about 25% more time than the reference's CBC call.
4. **No sandbox.** The solver runs in the same filesystem as the evaluator.
   - It could read `eval/test/instances.json` during the hidden run and spend one instance's budget working on others. The total budget is unchanged.
   - It could kill or disturb the evaluator process. A killed evaluator writes no score file and the script fails; tampering with the score file is overwritten (tested). Editing instance files mid-run has no effect, because instances are loaded before any solver starts.
   - No further defenses were built.
5. **Paper anchors.** The paper reports no family means, but `validate.py` needs a numeric `swot` value per experiment. Each `swot` entry therefore carries the paper's closest *non-peak* number at a setting inside the family, labelled as not a target:

   | Experiment | Anchor |
   |---|---|
   | `allreduce_scaling` | 39.6% (Fig. 8a, 64 nodes) |
   | `collective_algorithms` | 45.5% (Fig. 8b, Pairwise All-to-All, 10 nodes, k=4) |
   | `hardware_sensitivity` | 46.9% (Fig. 8a, AllReduce at k=4 and 0.2 ms, 512 nodes) |

   - An earlier draft of this iteration used a Fig. 7 *peak* (87.1%) and the 8-node example (20%) as anchors. Those are not on the scale of a family mean, and `--post-design` flagged them.
   - The peaks, the Fig. 5 example and every other paper number are kept unchanged under `_` keys.
   - The setup and scores were not changed.
6. **Weak separation in `hardware_sensitivity`.** See §5. I lowered its weight instead of enlarging it, because enlarging means another full reference-plus-variants cycle (≈2 min per instance per method on 1 CPU), and the compute was not available.

## 4. Reference score before → after

- **Before** (old test, suffix-span metric). Hidden CCT 500 / 1106.7 / 1202.5 µs; reduction 28.57 / 22.88 / 42.72%; valid 1.
  - On the paper instances (full CCT): Fig. 5 1200 µs (20%), Fig. 8 64-node 1840 µs (35.9%), 512-node 2431.7 µs (42.1%).
- **After** (hidden families, full-collective CCT). 37.93 / 46.93 / 43.71% (`allreduce_scaling` / `collective_algorithms` / `hardware_sensitivity`); valid 1 / 1 / 1.
  - Train: 41.19 / 37.67 / 41.68%.
  - Paper instances (`scoring/scores.json`) against the paper's numbers:

    | Instance | Reference | Paper |
    |---|---|---|
    | Fig. 5, 8 nodes | 1500 → **1200 µs (20.0%)** | 1500 → 1200 µs (20%) |
    | Fig. 8, 64 nodes | **1766.7 µs (38.4%)** | 39.6% |
    | Fig. 8, 512 nodes | **3140 µs (25.2%)** | 46.9% |

    The 512-node result is far below the paper's 46.9%. The identical workload scored 41.6% earlier in the same job; this is the time-limit variance in item 2 of §3, and I did not rerun until a good draw.
- The paper's claim (lower CCT than Strawman-ICR) holds in every family and on every paper instance, and the reference is never worse than lockstep on any instance.

## 5. Headroom check

- **At the bound.** The reference sits at the bound only for `valid_schedule` (= 1 in all three experiments), which is the constraint metric. `cct_reduction_vs_strawman_pct` is below what other methods reach in every experiment:
  - the MILP+LNS variant exceeds it in all three;
  - the local search exceeds it in two;
  - transmission-only lower bounds leave more room still.
- **Saturated instances.** Three of the six `hardware_sensitivity` test instances tie across every MILP-based run:
  - two k=2, 16-step instances that CBC solves to proven optimality in ~70 s;
  - the 20 ms-switching instance, at 96.0% (the local search reaches only 85.2% there).

  Two more are 20 µs-switching instances where no method gains more than 1% over lockstep. That leaves one instance with real spread, where the seed-2 rerun alone moves the result by 7 points. So the experiment's positive-control gain (+1.2) is within seed noise (1.36), hence weight 0.2.
- **Where the paper's method falls short.** `collective_algorithms` uses k=8, which the paper itself (§4.3.1) names as the regime where its 120 s solver returns sub-optimal schedules; it is part of the scored set, at weight 0.4. That is where the reference leaves the most room (+8.3 for LNS, +9.7 for local search). Many-step AllReduce (up to 20 steps at 1024 nodes) adds more (+7.6).
- **Brute force.** Enumerating plane-use patterns with one LP each is infeasible on every test instance (≥2.15e7 patterns after symmetry, against a 150 s budget). The 6-step paper example that the redteam enumerated (729 patterns) is now an unscored check.
- **Simple baselines.** Lockstep Strawman-ICR scores 0%, and the 10 s MILP scores 10–43%, both clearly below the reference's 38–47%, with room above (positive control 45–55%).

## 6. Reproduce

- `bash scripts/run.sh` regenerates `scoring/scores.json`, `scores_train.json` and `scores_test.json` from the reference (≈80 min on 1 CPU), then validates.
- `python -m hardening.harness all` replays this check. It resumes after preemption; completed runs are skipped.
- `python validate.py` passes.

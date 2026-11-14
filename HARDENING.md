# Hardening report (iteration 13)

**Bottom line.** Better schedules score higher than the reference by far more than seed noise, and worse ones score lower. All numbers below come from the final job (`639fc439-4b8`).

**The reference is now free of wall-clock time.**
- CBC never receives a time limit.
- PuLP is pinned to 3.3.2.
- Two independent runs of the hidden test, each with nothing else running, produced identical scores (`hardening/final_runs/_determinism.json`).
- A run with every CPU loaded twice over produced the identical schedule (`hardening/iter13_results/smoke.jsonl`).

**The reviewer's two findings did not reproduce.**
- Run alone, the corrected reference gives exactly the stored 32.08 / 26.87 on `allreduce_scaling` / `high_optical_degree`. The reviewer reported 45.62 / 40.33 / 34.57, which are the positive control's numbers, not the reference's.
- Headroom is therefore intact. The positive control beats the reference by +11.8 ± 1.5 points (30 wins, 0 losses), while CBC seed noise is +1.1 to +1.5.

**Other changes.**
- One hardware-grid cell where the 15-line relay rule beat the reference (Pairwise All-to-All, k=4) now holds ReduceScatter. The relay rule is now below the reference in every family.
- If a solver kills the evaluator, the result is now a failed run (worst values) instead of a missing, skipped entry.

**How runs were made.** Every run executes exactly what `scripts/evaluate_test.sh` executes (`python -m eval.test.evaluate`, no other arguments) in a private copy of `eval/` (`hardening/harness.py`). Raw logs and score files are in `hardening/final_runs/<run>/`; tables are in `hardening/results.md` and `hardening/summary.json`.

**Rank** (`hardening/analyze.py`). For every experiment and metric:

  weight × |coefficient| × direction × (candidate − reference) / population std

- Missing values are skipped.
- The population is the honest runs: reference, CBC seeds 2 and 3, hybrid, annealing, 1/10-node MILP, lockstep and relay rule.
- A shortcut's rank adds the shortcut itself to the population.

## What changed

### 1. Reference: no wall-clock time anywhere in its path (REVIEW item 1)

- **Before.** `method/swot_scheduler.py` passed CBC a 112 s `sec` limit as a safety stop next to the node budget. PuLP sends `sec` as a wall-clock limit (`timeMode elapsed`), so under load the reference could stop early.
- **CBC gets no time limit.** It now gets only the node budget from `method/budget.json`, which is unchanged: 5800 nodes up to 14 steps, scaled by (14/steps)² beyond that.
- **No wall clock even in logs.** CBC is told to keep CPU time (`timeMode cpu`), so even its own log never reads the wall clock.
- **One safety stop, outside CBC.** If CBC ever ran past its CPU allowance, which is the evaluator's 120 CPU-s minus 8 s minus model building, the kernel would kill it (an RLIMIT_CPU kill switch, `cpu_cap` in `method/swot_scheduler.py`). The lockstep schedule would then be written. It never fired on a scored instance: the reference used at most 90.3 CPU-s on test and 100.0 on train.
- **Removed `--max-nodes 0`.** That time-limit-only variant is gone; a positive node budget is required.
- **PuLP pinned.** `environment/setup.sh` now installs `pulp==3.3.2`, whose bundled CBC binary decides the schedules. It was unpinned, so a freshly built container could have drawn a different CBC.
- **Same fix for the positive control.** `hardening/swot_hybrid.py` uses the same node-only CBC calls. Its between-call safety checks count CPU time.
- **Calibration script adapted.** `hardening/calibrate.py` now probes with the kill switch instead of a CBC time limit.
- **Obsolete helper removed.** `hardening/swot_lns.py` (iteration 11's control, wall-clock based) is deleted.

**Evidence.**
- *Two independent runs.* The final job ran the reference twice. The first run was `scripts/run.sh` → `evaluate_test.sh`, which wrote `scoring/scores_test.json`. The second was `hardening/harness.py` in a private copy. Each ran with nothing beside it, and their results are identical in every experiment (`_determinism.json`). Per-instance CPU differed by up to ~10% between the runs (max 90.3 vs 83.1 CPU-s), but the schedules did not.
- *Under full CPU load.* In the design job, a 1500-node solve took 33.7 s alone and 107.5 s with 16 busy processes on 8 CPUs. The schedule was identical (`smoke.jsonl`).
- *Against the stored numbers.* On the 33 test instances that did not change, the per-instance reductions equal the iteration-12 stored ones. The three family means match the stored file to every digit except the changed hardware cell.

### 2. The reviewer's "reference = hybrid" did not reproduce (REVIEW items 1 and 2)

The design job (`76e1f0b4-e24`, `hardening/iter13_results/results.jsonl`) ran the corrected reference alone on the unchanged test instances. The final job did it twice more.

| Family (test, old instance set) | Reference, stored (iter. 12) | Reference, corrected, alone | Hybrid | REVIEW's "reference" |
|---|---:|---:|---:|---:|
| allreduce_scaling | 32.077 | **32.077** | 45.616 | 45.62 |
| high_optical_degree | 26.875 | **26.875** | 40.331 | 40.33 |
| hardware_sensitivity | 24.291 | **24.291** | 34.571 | 34.57 |

- Per instance, the corrected reference differs from the hybrid on 30 of 34 instances. I cannot reconstruct the reviewer's environment.
- Their numbers equal the hybrid's to every digit. That points to the hybrid having been scored as `swot` (or a cached hybrid output), not to a stronger uncontended reference.
- Whatever the cause, both possible sources of drift are now closed: a wall-clock limit, and an unpinned CBC binary.

### 3. Headroom re-checked against the corrected reference (REVIEW item 2)

Before keeping the old families I tested three new candidate families where the paper's solver is expected to fall short. I drew 12–15 hidden-test instances each and ran the corrected reference alone.

| Candidate (test draw) | Reference | Relay rule | Annealing | Hybrid | Verdict |
|---|---:|---:|---:|---:|---|
| AllReduce, k=8, 64–16384 nodes (Fig. 7(b), §4.3.1) | 0.31 (lockstep on 14/15: no incumbent or kill switch) | 16.08 | – | – | not scorable |
| AllReduce, k=4, 2048–16384 nodes (Fig. 8(a) extended) | 9.38 (no incumbent on 5/12) | 11.60 | 34.76 | 35.56 | not scorable |
| ReduceScatter, k=8, 2048–16384 nodes | 17.91 (kill switch on 2/12) | 20.38 | 42.83 | 44.22 | not scorable |

- In all three, the 15-line relay rule scores above the reference. So does the gym's own rule: a hand-written rule outranking the reference is a flaw in the test.
- On the k=8 AllReduce family the paper's MILP is essentially the lockstep baseline. There is plenty of room for better methods (annealing reaches 35–43%), but a fixed pattern would be rewarded too.
- These instances were dropped from both slices. The results are kept in `hardening/iter13_results/results.jsonl`, with no instance properties for test rows. They also back the scope notes in `scoring/EXPERIMENTS.md` and `scoring/DIRECTION.md`.
- The existing families keep clear headroom against the corrected reference (§5), so no experiment was added.

### 4. Hardware grid: Pairwise All-to-All at k=4 replaced by ReduceScatter (relay-rule tie, iteration-12 §3.1)

Iteration 12 left the relay rule tying the reference on `hardware_sensitivity` (25.04 vs 24.29).

**The cause was one cell.** Pairwise All-to-All at k=4 with 20 ms switching (te30):
- The relay rule reaches the best known schedule there (46.69, the same as annealing and hybrid).
- The paper's MILP reaches 26.85.

All-distinct, uniform-volume collectives on many planes are the structure the gym already excluded for Bruck at k=4 and for every all-to-all at k=8. So I excluded Pairwise at k=4 too.

**How the cell was replaced.**
- The generator now places ReduceScatter in that cell and still consumes the same random draw.
- So exactly one instance per slice changed (te30 and tr30). All other 33 + 33 instances are byte-identical, checked by diff.

On the new te30 the reference scores 40.06, the relay rule 23.03, annealing 37.75 and the hybrid 42.34. The relay rule is now below the reference on `hardware_sensitivity` on both slices:

| Slice | Relay rule | Reference |
|---|---:|---:|
| Test | 23.07 | 25.39 |
| Train | 22.59 | 24.82 |

### 5. Evaluator: a killed evaluator now scores as failed

**The gap.** Before, a solver that killed the evaluator process (`kill -9 $PPID`) left no `scores_test.json`. Ranking skips missing values, so failing that way cost nothing.

**The fix.** Both evaluators now write the output file before any solver runs, with every discovered method at its worst value and `_metadata.incomplete` set. They replace it atomically only after every method is scored.

**Result.** The new probe `shortcut_kill_evaluator` now scores −100 / 0 in every experiment (rank −6.29). The train and test evaluators are still separate copies.

### 6. Harness

`hardening/harness.py` now runs:
- the reference first, alone;
- every other run in a pool of 4 processes, each with its own private copy of `eval/`;
- an append-only per-run cache, so a preempted job resumes.

The job was preempted three times. Cached outputs replayed after a restart come from the same deterministic code, but their CPU shows as ≈0, so the CPU figures below cover only instances that actually ran.

Other changes:
- The iteration-12 runs are archived in `hardening/iter12_final_runs/`, `iter12_results.md` and `iter12_summary.json`.
- The time-limited "more compute" variant is gone; it is incompatible with a reference that has no time limit.
- Full-budget annealing (`shortcut_private_search`) is replaced by deterministic annealing (`anneal_fixed`, 500k moves, 9–16 CPU-s). Both give exactly 44.75 / 38.59 on the two unchanged families, so the extra budget bought nothing.

## 1. Do better results score higher?

Hidden test, paired on the same 34 instances; % reduction vs Strawman-ICR.

| Run | allreduce_scaling | high_optical_degree | hardware_sensitivity | Rank | Paired Δ vs reference, all 34 (wins/losses) |
|---|---:|---:|---:|---:|---|
| **Reference** (paper MILP, node budget, alone) | 32.08 | 26.87 | 25.39 | 0 | — |
| Reference, CBC seed 2 (noise) | 33.24 | 28.59 | 27.09 | +0.13 | +1.55 ± 1.32 (19/11) |
| Reference, CBC seed 3 (noise) | 34.34 | 26.27 | 27.32 | +0.11 | +1.13 ± 1.33 (16/14) |
| **Better: hybrid** (annealing + LP polish + MILP neighbourhoods; 44 CPU-s mean vs the reference's 39) | **45.62** | **40.33** | **34.19** | **+1.01** | **+11.84 ± 1.50 (30/0)** |
| Better: annealing (deterministic, 9–16 CPU-s) | 44.75 | 38.59 | 32.47 | +0.89 | +10.36 ± 1.44 (28/3) |
| Relay rule (15 lines) | 28.63 | 23.21 | 23.07 | −0.27 | −3.13 ± 1.04 (7/24) |
| Weaker: same MILP, 1/10 of the nodes | 22.34 | 18.64 | 20.28 | −0.65 | −7.57 ± 1.73 (0/28) |
| Weaker: lockstep (= Strawman-ICR) | 0 | 0 | 0 | −2.40 | −27.88 ± 3.22 (0/34) |

Per family, the hybrid's gain against seed noise:

| Experiment | Hybrid gain (± stderr) | Seed 2 / seed 3 shift |
|---|---:|---:|
| `allreduce_scaling` | +13.5 ± 2.5 | +1.2 / +2.3 |
| `high_optical_degree` | +13.5 ± 2.4 | +1.7 / −0.6 |
| `hardware_sensitivity` | +8.8 ± 2.8 | +1.7 / +1.9 |

The ordering is the expected one: hybrid > annealing > reference ≈ its seed variants > relay rule > 1/10-node MILP > lockstep.

Before → after, for the variants (iteration 12 → 13):

| Run | Rank (iteration 12 → 13) |
|---|---|
| Hybrid | +1.11 → +1.01 |
| Annealing | +0.99 → +0.89 |
| Relay | −0.18 → −0.27 |
| 1/10 nodes | −0.70 → −0.65 |
| Lockstep | −2.49 → −2.40 |

The raw values change only on `hardware_sensitivity` (the te30 swap).

Train vs test:

| Method | Train | Test |
|---|---|---|
| Reference | 33.40 / 25.12 / 24.82 | 32.08 / 26.87 / 25.39 |
| Hybrid | 46.56 / 39.45 / 33.25 | 45.62 / 40.33 / 34.19 |
| Relay rule | 29.19 / 21.61 / 22.59 | 28.63 / 23.21 / 23.07 |

Train and test agree within 1.8 points for every method.

## 2. Major shortcuts: fix and score before → after

Every probe was rerun through the hidden-test evaluator in this iteration.

| Shortcut | Fix | Before | After |
|---|---|---|---|
| scalar_claims, empty_schedule, impossible_scalars, empty_entry, null | Only `schedule` is read; missing or empty fails the run (iteration 11). | REDTEAM: +4.0 to +10.7 | Failed: −100 / valid 0 everywhere, rank −6.29 |
| invalid_fast, zero_duration | `t_end − t_start ≥ d/B + T_lat` | REDTEAM: +1.2 / +2.8 | Failed |
| extra_planes, spec_override | Plane index < k from the evaluator's frozen instance | REDTEAM: +3.9 | Failed |
| baseline_inflation, claimed_fields_ignored, tamper_scores, replay | Baseline computed by the evaluator; claims ignored; output written atomically; hidden instances | REDTEAM: +1.8 / tie | Lockstep value 0.00%, rank −2.04 |
| late_prefix | CCT measured from time 0 | REDTEAM: tie | −100% per instance (valid), rank −3.10 |
| omit, drop_experiment, timeout | `swot` always scored; any failed instance fails all experiments | REDTEAM: tie | Failed |
| cpu_escape (two detached helpers × 65 CPU-s) | Subreaper + counted CPU over the process tree | Iteration 12: failed | Failed (130 CPU-s counted) |
| **new: kill_evaluator** (`kill -9 $PPID`) | Output file pre-written with every method failed (§5) | No file → skipped, costs nothing | **Failed: −100 / 0 everywhere, rank −6.29** |
| **Relay rule ≥ reference on `hardware_sensitivity`** | Pairwise k=4 cell → ReduceScatter (§4) | 25.04 vs 24.29 | **23.07 vs 25.39**; below the reference in every family |
| Brute force over plane-use patterns | Instances far too large to enumerate (k=4 AllReduce: 15¹²–15²⁰ patterns; k=8 ReduceScatter: 255⁷–255¹⁰) | REDTEAM: tie on a 3⁶ example | Not applicable |

## 3. Shortcuts and weaknesses left, and why

1. **No sandbox.**
   - A solver runs as the same user, in the same filesystem as the evaluator.
   - During the hidden run it could read `eval/test/instances.json`. With state on disk it could then shift CPU budget between instances: the per-instance count still applies, but work done during one call could serve another instance.
   - It could also write a fake `scoring/scores_test.json` and then kill the evaluator. Kill alone is now penalized (§5); kill plus forgery is not.
   - Both are deliberate tampering that the separate grader should catch. Closing them needs process isolation, which is not a small fix.
2. **Machine speed.**
   - The reference is deterministic, but its CPU use is not: max 90.3 CPU-s on test and 100.0 on one train instance (tr07), against the kill switch at about 110 CPU-s.
   - On a CPU about 10% slower than the compute node, tr07 would fall back to lockstep. On one about 20% slower, te14 and te22 would too.
   - The stored scores come from this cluster's nodes. Shrinking the node budget would change the reproduced method, so I left it. Other methods are bounded by counted CPU time and do more search on faster machines, as before.
3. **Annealing is close to the positive control.**
   - Deterministic annealing over plane-use patterns ranks +0.89, against +1.01 for the hybrid. The hybrid leads by 1.5 points paired, at 3–5× the CPU.
   - It is about 40 lines in `hardening/candidates.py`, so a future attempt could copy it.
   - I count it as an honest alternative scheduler (local search instead of a MILP, at a quarter to two fifths of the reference's CPU: 9–16 vs 39 CPU-s), not a shortcut. It is a real scientific counterpoint to the paper's claim that off-the-shelf MILP solving needs no specialized heuristics.
   - No hand-written rule or closed form reaches the reference.
4. **Unscored settings.**
   - Not scored: AllReduce, Bruck and Pairwise at k=8; Bruck and Pairwise at k=4; anything beyond 1024 nodes.
   - On all of these, a fixed relay rule matches or beats the paper's budget-limited MILP (§3; iteration 12 for the k=8 all-to-alls and Bruck at k=4).
   - The test therefore covers one of Fig. 7's four algorithms at k=8.

## 4. Reference score before → after

| Slice | Before (iteration 12, stored) | After (iteration 13, alone, no wall clock) |
|---|---|---|
| Hidden test | 32.08 / 26.87 / 24.29 | 32.08 / 26.87 / **25.39** |
| Train | 33.40 / 25.12 / 25.26 | 33.40 / 25.12 / **24.82** |

- The only change is the replaced hardware cell (te30 / tr30). The 33 + 33 other instances are bit-identical.
- `valid_schedule` = 1 everywhere.
- Paper instances (`scoring/scores.json`, unscored) are unchanged:

  | Instance | Reproduced | Paper |
  |---|---|---|
  | Fig. 5, 8 nodes | **1200 µs (20.0%)** | 1500 → 1200 µs |
  | Fig. 8, 64 nodes | **38.2%** | 39.6% |
  | Fig. 8, 512 nodes | **41.6%** | 46.9% |

- The paper's direction (large reductions over Strawman-ICR) holds in every family and on every paper instance. The reference is never worse than lockstep on any instance.
- The paper's numbers in `scoring/reference.json` are unchanged.
- **Weights unchanged** (0.4 / 0.3 / 0.3): every family still separates the positive control from the reference by more than seed noise, so nothing argued for moving them.

## 5. Headroom check

- **At the bound.** The reference sits at the bound only for `valid_schedule` (1 everywhere), which is the constraint metric.
- **Room above it.** `cct_reduction_vs_strawman_pct` is 8.8–13.5 points below the hybrid in every family. The hybrid uses about the reference's CPU (44 vs 39 CPU-s mean per instance, design job, all 34 instances) and is not proven optimal; annealing also beats the reference.
- **Simple baselines.**

  | Baseline | Score range |
  |---|---|
  | Lockstep | 0 |
  | Relay rule | 23.1–28.6 |
  | 1/10-node MILP | 18.6–22.3 |
  | Reference | 25.4–32.1 |
  | Hybrid | 34.2–45.6 |

  So there is room both below and above the reference.
- **Brute force** over plane-use patterns is infeasible on every scored instance.
- **No experiment added.** I measured three candidate families from where the paper's method falls short (§3). In all three a 15-line rule beats the reference, so none was added; the existing families already have the headroom.

## 6. Could not fix

1. **No sandbox** (§3.1). A solver can still read the hidden instance file, or forge the score file and then kill the evaluator.
2. **Machine-speed margin** of the reference's CPU kill switch (§3.2).
3. **The 512-node Fig. 8 point** reproduces at 41.6% against the paper's 46.9%.
4. **REVIEW item 1 did not reproduce** (§2), and I cannot inspect the environment that gave 45.62 / 40.33 / 34.57. What changed regardless: CBC no longer sees any time limit, and PuLP/CBC is pinned.
5. **Preemptions.** The final job was preempted three times. Replayed outputs are deterministic and unchanged, but their CPU is not measured; CPU figures above cover only instances that actually ran.

## 7. Reproduce

- `bash scripts/run.sh` regenerates the reference outputs from scratch and validates:
  - `scoring/scores.json` and `scoring/scores_train.json`, about 25 min;
  - `scoring/scores_test.json`, about 25 min.
- `python -m hardening.harness all` replays this check: a second reference run, the variants and the probes. It takes about 2 h on 4 CPUs and resumes after preemption.
- `python -m hardening.iter13 summary` prints the design-run tables.

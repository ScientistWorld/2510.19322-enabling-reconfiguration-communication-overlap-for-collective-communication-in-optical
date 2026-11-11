# Does this gym reward better research?

**Not reliably.** A genuinely stronger solve improves the hidden score, but its aggregate gain (**+0.458484**) is smaller than the three-seed spread (**0.811424**). A clearly weaker scheduler scores **−4.290785**. More decisively, the test can rank an explicitly invalid schedule above the reference, accept fabricated results, and tie a schedule whose real completion time is delayed by one million microseconds. The reproduction does beat its lockstep baseline in the paper's direction; the main failures are in what the hidden test measures and accepts.

## Better and weaker methods

All triples below are ordered **8 / 64 / 512 nodes**. Times are microseconds. The reference is the `swot` result in the original `scoring/scores_test.json`, preserved in [initial_state](redteam/initial_state/scores_test.json). Its regenerated default run matches every hidden metric exactly.

| Actual method variant | Full collective completion time | Hidden-test CCT | Hidden reconfigurations | Aggregate improvement over reference |
|---|---|---|---|---:|
| [Reference, regenerated](redteam/reference_default/run.sh) | 1200 / 1840 / 2431.6667 | 500 / 1106.66666 / 1202.5 | 2 / 8 / 10 | 0 |
| [Stronger solve](redteam/better_solver/run.sh) | 1200 / 1672.5 / 2169.1667 | 500 / 952.5 / 1039.1667 | 2 / 8 / 11 | +0.458484 |
| [Weaker lockstep](redteam/weaker_lockstep/run.sh) | 1500 / 2870 / 4198.75 | 700 / 1435 / 2099.375 | 4 / 20 / 32 | −4.290785 |

The stronger variant uses the same MILP, adds a valid symmetry constraint ordering the first step's message allocations across interchangeable planes, and raises CBC's time limit from 120 to 600 seconds per experiment. This is an explicit compute increase for the positive control, departing from the paper's 120-second setting. The weaker variant removes uneven splitting, early reconfiguration and topology bypassing. Both produce full schedules with correct volumes, plane limits, transmission durations, circuit delays and barriers. Independent duration checks differ from the physical formula by at most 0.00008 us from serialization rounding. Artifacts, diagnostics, emitted test scores and return codes are saved in each variant's directory.

The stronger variant gains 154.16666 us on the 64-node test, below its 435.00003 us seed spread. Its 163.3333 us gain at 512 nodes exceeds that workload's 35.6944 us spread. Its aggregate gain does **not** exceed aggregate seed spread. The weaker variant's aggregate loss does. Thus the weak negative control passes, while the requested robust positive control is not established.

The score also reverses a real quality comparison: seed 3 finishes the full 64- and 512-node collectives at **1865 / 2514.1667**, both worse than **1840 / 2431.6667**, yet ranks **+0.063205**. It has a shorter measured 64-node suffix and fewer counted reconfigurations. This small rank gain is within seed noise, but the metric mismatch itself is deterministic: the test scores a suffix span rather than the paper's complete collective CCT.

### How aggregate scores were calculated

For every scored experiment and metric, [analyze.py](redteam/analyze.py) sums

`experiment_weight × abs(coefficient) × direction × (candidate − reference) / metric_std`.

`direction` is +1 for `higher_is_better`, otherwise −1. Missing values are skipped as specified. Negative coefficient signs are **not** applied again. Standard deviations are population standard deviations over explicitly stated attempts; a constant metric contributes zero. These are conditional audit ranks, since the eventual population of future attempts is unknown. Raw values in each `scores_test.json` are the actual hidden-test output and do not depend on this calculation.

The quality and seed tables use one fixed six-attempt population: original reference, seeds 1–3, stronger solve and weaker lockstep. The shortcut table uses those six **plus the shortcut being tested**, so failed validity and other newly varying metrics receive their penalties. Reference improvement is zero throughout. [summary.json](redteam/summary.json) also preserves pairwise and all-audit populations. The fixed-quality-population column is only used for honest quality comparisons; its constant correctness metrics cannot assess a newly invalid candidate. Extreme failed attempts dramatically increase standard deviations in an all-audit population, which is why no universal numeric rank is asserted. Changing units does not increase a metric's weight under this normalization.

## Seed spread and reproduction

Three independent reference reruns retain the original 120-second limit and set both CBC `randomSeed` and `randomCbcSeed` to 1, 2 or 3.

| Run | Hidden CCT, 8 / 64 / 512 | Reduction versus strawman, % | Reconfigurations | Aggregate improvement |
|---|---|---|---|---:|
| [Seed 1](redteam/reference_seed_1/scores_test.json) | 500 / 1280.00003 / 1388.4723 | 28.571429 / 10.801392 / 33.862588 | 2 / 7 / 15 | −0.554994 |
| [Seed 2](redteam/reference_seed_2/scores_test.json) | 500 / 845 / 1411.6666 | 28.571429 / 41.114983 / 32.757768 | 2 / 6 / 11 | +0.256430 |
| [Seed 3](redteam/reference_seed_3/scores_test.json) | 500 / 950 / 1424.1667 | 28.571429 / 33.797909 / 32.162348 | 2 / 5 / 11 | +0.063205 |
| Max minus min | **0 / 435.00003 / 35.6944** | **0 / 30.313591 / 1.700239** percentage points | **0 / 2 / 4** | **0.811424** |

All seed runs have validity 1, zero volume error and zero overlap, so their spreads in those metrics are zero. These are observed three-seed ranges, not confidence intervals. The default reference's 512-node result is better than all three explicit seeds; including the default would widen that workload's observed range. Gains smaller than the reported spread are noise for this audit.

The full-collective reproduction has the correct direction:

| Workload | Strawman full CCT | Reproduced full CCT | Reproduced reduction | Paper reduction |
|---|---:|---:|---:|---:|
| Fig. 5, 8 nodes | 1500 | 1200 | 20% | 20% |
| Fig. 8, 64 nodes | 2870 | 1840 | 35.888502% | 39.6% |
| Fig. 8, 512 nodes | 4198.75 | 2431.6667 | 42.085937% | 46.9% |

The actual implementation contains the paper's key computation: MILP variables for heterogeneous message allocations, asynchronous per-plane reconfiguration and transmission, topology bypassing, and logical step barriers. It is not a learned surrogate. The following departures and limits matter:

- Only three fixed Rabenseifner AllReduce workloads are scored. Other collectives, message-size sweeps, optical degrees, switching-delay sweeps and the paper's One-shot and Ideal comparisons are absent.
- The MILP uses explicit plane-use binaries, big-M inequalities and pairwise previous-use implications for configuration state, rather than the paper's displayed `last_cfg`/same-configuration formulation. It forces first use to have no reconfiguration cost and suppresses redundant same-configuration reconfigurations. These are concrete implementation choices within the intended scheduling procedure. The positive-use lower bound is 0.000001 MB.
- Each workload represents a configuration by an integer ID and a per-step message volume. There is no replay of node-to-node traffic or runtime execution plan. The paper's MILP also schedules at the step/plane level; this abstraction alone is not evidence of an algorithm substitution. The gym evaluates the numerical model, not the runtime shim described in section 3.3.
- The reference uses the paper's CBC/PuLP and 120-second limit, but no pinned solver randomness. The 64- and 512-node gains fall short of the reported values. There is no basis to claim identical incumbent solutions or global optimality at those time limits.
- Most importantly, the hidden score selects only steps 5–6 of the six-step example, the last six of twelve at 64 nodes and the last nine of eighteen at 512 nodes. It subtracts the earliest activity start within that suffix. The paper optimizes the entire collective's finish time from its start. The paper's whole-collective results are not the hidden reference values.

These are deterministic analytical workloads generated from visible code, not a sampled real-world dataset. The three active settings retain the advertised node counts and network parameters; the helper's name/docstring about scaling does not mean the active 512-node case was reduced to 16 nodes. The synthetic workloads retain the paper's local effect: removing splitting/overlap/bypassing worsens full CCT substantially, and the reference is better than lockstep. What fails is the implication that a better hidden suffix score must be a better complete-collective method. No unseen workloads test generalization.

## Shortcut runs

Every row links its executable `run.sh` and the actual [test output](redteam/results.md). “Works” means strictly above or tied with the reference without a better method; ties are explicitly labeled shortcuts. Reference CCT is **500 / 1106.66666 / 1202.5**, validity **1 / 1 / 1**, aggregate improvement **0**. The rank column uses the six honest attempts plus that row's candidate, as defined above.

| Shortcut and executable | What it does | Hidden result versus reference | Aggregate improvement | Works or fails |
|---|---|---|---:|---|
| [shortcut_scalar_claims](redteam/shortcut_scalar_claims/run.sh) | Writes CCT 0, validity 1, events/error/overlap 0 with no schedule. | [CCT 0 / 0 / 0, validity 1](redteam/shortcut_scalar_claims/scores_test.json) | +4.017501 | **Works:** metrics trusted without evidence. |
| [shortcut_empty_schedule](redteam/shortcut_empty_schedule/run.sh) | Same claims with `schedule: []`. | [CCT 0 / 0 / 0, validity 1](redteam/shortcut_empty_schedule/scores_test.json) | +4.017501 | **Works:** empty output uses the scalar fallback. |
| [shortcut_impossible_scalars](redteam/shortcut_impossible_scalars/run.sh) | Writes CCT/events/error/overlap −1e9 and validity 2. | [Impossible values retained in every experiment](redteam/shortcut_impossible_scalars/scores_test.json) | +10.716517 | **Works:** no range checks or schedule evidence. |
| [shortcut_invalid_fast](redteam/shortcut_invalid_fast/run.sh) | Keeps full volumes/configurations but sets all times and switching flags to zero. | [CCT 0 / 0 / 0, actual evaluator validity 0](redteam/shortcut_invalid_fast/scores_test.json) | +1.159763 | **Works:** benefit outweighs the explicit failure penalty. |
| [shortcut_zero_duration](redteam/shortcut_zero_duration/run.sh) | Preserves real plane assignments, reconfiguration delays and barriers but transmits every volume in zero time. | [CCT 200 / 600 / 800, validity 1](redteam/shortcut_zero_duration/scores_test.json) | +2.799327 | **Works:** transmission time is unchecked. |
| [shortcut_extra_planes](redteam/shortcut_extra_planes/run.sh) | Allocates 100 dedicated planes per required configuration, despite fixed limits of 2/4/4. | [CCT 6 / 132.6 / 192.775, validity 1](redteam/shortcut_extra_planes/scores_test.json) | +3.933157 | **Works:** plane indices/count are unchecked. |
| [shortcut_fixed_spec](redteam/shortcut_fixed_spec/run.sh) | Replaces the supposedly fixed checkpoint specification with 300/600/900 planes, then uses them. | [Same fast CCT, validity 1; comparison also changes](redteam/shortcut_fixed_spec/scores_test.json) | +3.918739 | **Works:** evaluator takes the first artifact's specification. |
| [shortcut_baseline_inflation](redteam/shortcut_baseline_inflation/run.sh) | Replaces the baseline artifact with a schedule containing million-us inter-step delays; candidate unchanged. | [Original candidate CCT; reductions 99.9500% / 99.9779% / 99.9850%](redteam/shortcut_baseline_inflation/scores_test.json) | +1.787987 | **Works:** moves the comparison denominator. |
| [shortcut_late_prefix](redteam/shortcut_late_prefix/run.sh) | Adds 1e6 us to all schedule times. | [Reference suffix metrics, up to rounding](redteam/shortcut_late_prefix/scores_test.json); full CCT increases by 1e6 us. | ≈0 (2.4e−14) | **Works, shortcut tie:** worse completion time is invisible. |
| [shortcut_replay](redteam/shortcut_replay/run.sh) | Copies schedules freshly generated from visible workload definitions and the original method. | [Exactly the reference](redteam/shortcut_replay/scores_test.json) | 0 | **Works, shortcut tie:** honest offline-cache alternative the test cannot distinguish from new work. |
| [shortcut_bruteforce](redteam/shortcut_bruteforce/run.sh) | Enumerates every plane-use pattern for the central example, solves each continuous timing/allocation LP, reuses reference schedules for the other two. | [Exactly the reference](redteam/shortcut_bruteforce/scores_test.json) | 0 | **Works, shortcut tie:** central example solved by enumeration. |
| [shortcut_omit_all](redteam/shortcut_omit_all/run.sh) | Supplies `_swot` and a dummy named method; omits scored `swot` entirely. | [No `swot` values in any experiment](redteam/shortcut_omit_all/scores_test.json) | 0 | **Works, shortcut tie:** all losses skipped. |
| [shortcut_drop_one_experiment](redteam/shortcut_drop_one_experiment/run.sh) | Retains reference schedules at 8/64 nodes, omits `swot` at 512 nodes. | [512-node candidate omitted, not failed](redteam/shortcut_drop_one_experiment/scores_test.json) | 0 | **Works, shortcut tie:** incomplete task is unpenalized. |
| [shortcut_empty_entry](redteam/shortcut_empty_entry/run.sh) | Supplies `{}` as every candidate result. | [CCT/error/overlap 1e12, validity 0, but events 0](redteam/shortcut_empty_entry/scores_test.json) | −9.609129 | **Fails:** loses overall, though failure defaults are incomplete. |
| [shortcut_null](redteam/shortcut_null/run.sh) | Supplies JSON null as every result. | [CCT/events/error/overlap 1e12, validity 0](redteam/shortcut_null/scores_test.json) | −10.716518 | **Fails:** hidden test penalizes null; visible train evaluation crashes. |
| [shortcut_claimed_fields_ignored](redteam/shortcut_claimed_fields_ignored/run.sh) | Attaches impossible scalar claims to the real nonempty reference schedule. | [Exactly the recomputed reference metrics](redteam/shortcut_claimed_fields_ignored/scores_test.json) | 0 | **Shortcut tie through unchanged real output; scalar forgery fails** on the nonempty-schedule branch. |

### Why these shortcuts pay

**Correctness is not a prerequisite.** Even the evaluator's own `valid_schedule = 0` does not prevent positive rank: `shortcut_invalid_fast` is +1.159763 after including the validity penalty and normalizing all varying metrics. Its pairwise normalized rank is also positive (+1.5), so this is not an artifact of omitting the failing metric. A finite additive validity coefficient cannot enforce task feasibility against arbitrary benefits and changing cohort spreads.

**Physical checks are incomplete.** The validator checks per-step volumes, required configuration IDs, some circuit transitions, barriers and per-plane overlaps. It does not enforce `transmit_end − transmit_start = message / bandwidth + base_latency`, or plane IDs within `[0, k)`. Independent diagnostics show zero-duration schedules missing up to **300 / 293.333352 / 366.666668 us** of required transmission time per item. Extra-plane schedules use **300 / 600 / 900 distinct planes**, all accepted. The fixed-spec shortcut separately demonstrates that even an added plane-bound check would be insufficient if the trusted bound still comes from candidate checkpoints.

**The other side is mutable.** Baseline schedule results and experiment specifications are read from the same writable `checkpoints/` tree. The first specification encountered lexicographically wins; result entries are merged with later entries overwriting earlier ones. The baseline-inflation shortcut changes only the comparison: candidate CCT, validity, volume, overlap and event count remain exactly the reference, while every relative-improvement metric increases. This is a robust dominance shortcut under any positive finite normalization.

**The measured interval ignores arbitrarily bad prefix/start latency.** Full completion times in the late-prefix shortcut are **1001200 / 1001840 / 1002431.6667**, while its scores tie the reference. This is physically valid scheduling with a much worse paper objective, not merely trusting a claimed timing field.

**Public inputs determine the entire test.** All configurations, step volumes, resources and the complete sequence are in visible `data/collectives.py`; the solver already schedules the full workload. With only three deterministic instances, a future agent can regenerate and store all answers without any hidden file. Replay uses newly computed visible outputs, not the hidden reference. Offline caching is legitimate for the paper's deployment model, so this shortcut tie is an honest alternative rather than a false correctness claim; this test supplies no evidence of a new scheduling contribution.

**The central test is small enough for brute force.** [Enumeration evidence](redteam/shortcut_bruteforce/enumeration.json): all **729 = 3^6** nonempty two-plane use patterns were solved in **4.237 seconds**, finding full CCT **1200 us** and the same hidden metrics. The central workload, weighted 0.5, is too small to require the intended combinatorial machinery. This is not a claim that all three workloads were exhaustively solved: naive pattern counts are **15^12 = 129746337890625** and **15^18 = 1477891880035400390625** for the larger cases; their schedules were explicitly reused. The reference's central full-CCT optimum is saturated for this model, although its hidden suffix metrics are not at universal physical bounds.

## Bounds, missing results and coverage

Every scored metric already at its intended bound is listed here; there are nine experiment/metric pairs:

| Experiment | Metric already at bound | Reference value / bound |
|---|---|---:|
| 8 nodes | `valid_schedule` | 1, maximum |
| 8 nodes | `step_volume_error_mb` | 0, minimum |
| 8 nodes | `max_plane_overlap_us` | 0, minimum |
| 64 nodes | `valid_schedule` | 1, maximum |
| 64 nodes | `step_volume_error_mb` | 0, minimum |
| 64 nodes | `max_plane_overlap_us` | 0, minimum |
| 512 nodes | `valid_schedule` | 1, maximum |
| 512 nodes | `step_volume_error_mb` | 0, minimum |
| 512 nodes | `max_plane_overlap_us` | 0, minimum |

None of the reference's test CCTs is at zero, none of its reductions is 100%, and none of its event counts is zero. Ignoring reconfiguration entirely gives transmission-plus-base lower bounds **300 / 435 / 499.375 us** for the scored steps, below the reference. These are lower bounds, not demonstrated attainable schedules. The stronger valid variant actually beats the two larger reference CCTs; the weak baseline is substantially below the reference in rank. There is room above the reference, though the central full-collective optimum is already attained and the three correctness metrics have no valid improvement available. The scalar fallback incorrectly permits values beyond their intended bounds.

Missing-result handling does not meet the requested completeness rule. A present null receives worst sentinel values and a large negative derived percentage. A present empty object defaults to **zero reconfigurations**, rewarding that metric despite failure. An absent method or absent experiment receives **no result row**, so ranking skips it; deleting everything ties the reference instead of losing. An underscore-prefixed on-disk result is deliberately excluded. The dummy ordinary method in the omission run is emitted and penalized, proving ordinary method enumeration works, but **not every method on disk is written**, and no fixed method-by-experiment inventory is completed. The omission shortcut's zero rank follows the specified missing-value rule; a separate downstream rejection for missing method IDs would need to be explicit and tested.

With a fixed baseline, `cct_us` and percentage reduction are linear transforms of the same quantity. After standardization they count the same benefit twice with their respective coefficient magnitudes. Event counting also differs between the implicit strawman (global configuration changes) and serialized schedules (one event per optical plane). The weaker schedule's 4/20/32 events versus implicit-baseline 2/5/8 in the hidden suffix demonstrate that mismatch. These comparisons do not implement the briefing's “lower when CCT is comparable” qualification; event counts are always added to rank.

## Execution and scope

Twenty-two trials have saved scores and successful no-argument hidden-test return codes: default reference, three seeds, stronger and weaker variants, and sixteen shortcut checks. [Harness](redteam/harness.py), [candidate implementations](redteam/candidates.py), [all results](redteam/results.md) and [machine-readable summary](redteam/summary.json) are included. Each folder preserves the actual emitted `scores_test.json`, all JSON checkpoint artifacts, status and applicable physical diagnostics. Candidate construction uses only agent-visible inputs. The audit analysis reads the rubric/reference to report scores; candidate generation does not read those files, the paper or hidden evaluation code.

The runs execute the unchanged `bash scripts/evaluate_test.sh` with **no arguments**, in fresh subprocesses in the compute container after candidate generation exits. All shortcuts act solely through persisted artifacts, so no process needs to survive into the evaluator's fresh job. Evaluation code and Python environment are untouched. Each trial restores the original checkpoint tree, score files and temporary method module. The first job lost its worker after saving the default run; the resumed CPU job reused that completed reference and finished all remaining trials successfully. No expensive work was run on the login node.

The temporary `scripts/run.sh` is restored to the iteration's starting git version. All audit-authored changes are under `redteam/` and this report, apart from the required final `action.yaml` signal. The pre-existing README/manifest device files and trajectory deletions recorded in [starting status](redteam/initial_state/starting_status.txt), and subsequent system-owned job/trajectory changes, are preserved.

Next iteration should recompute every metric from a required nonempty schedule, validate physical resource and timing equations against immutable workload definitions, freeze/recompute the baseline independently, fill every required method/experiment failure, gate all benefits on feasibility, and score complete collective CCT. Add varied hidden workloads large enough that one worked example or finite replay table cannot stand in for a scheduling method.

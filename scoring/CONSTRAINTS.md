# Scientist Constraints

## Interface

A method is a solver script `scripts/solvers/<method>.sh INSTANCE_JSON OUTPUT_JSON TIME_LIMIT_S` that writes `{"schedule": [...]}` (format in `briefing/evaluation.md`). The scored key is `swot` (`scripts/solvers/swot.sh`). The solver receives one instance at a time and the paper's 120 s limit; it is killed 150 s after it starts.

## Workload and resources are fixed by the evaluator

Instances, optical degree `k`, per-plane bandwidth (800/k Gbps), base latency, switching latency and the baseline are all taken from the evaluator's frozen copies (`eval/train/`, `eval/test/`). Anything the solver writes besides the schedule (specs, CCTs, validity flags, baselines, files under `checkpoints/`) is ignored. Using more planes, more bandwidth or faster switching is resource scaling, not scheduling, and is rejected as an invalid schedule.

## Correctness (checked on every instance)

- Per-step volume conservation, with a positive volume on every listed transmission.
- Plane indices in `[0, k)`, at most one entry per (step, plane).
- Transmission time of at least `d/B + T_lat`.
- Topology switching of at least `T_recfg` whenever a plane's topology changes. A plane's first use needs no switch.
- No switching while transmitting, and no transmission before the circuit is ready.
- Step barriers.
- CCT is measured from time 0.

One violation, timeout, crash or missing output on any instance fails the whole run, which gets the worst value in every metric of every experiment.

## Budget

Search is allowed only inside the per-instance time limit, on the instance given. Precomputing answers for the public train or paper instances does not help on the held-out instances.

## Compliance Checklist

- [ ] `scripts/solvers/swot.sh` produces a valid schedule for every train instance within 120 s (`bash scripts/evaluate_train.sh` shows `valid_schedule = 1` everywhere)
- [ ] No change to `eval/`, the instance files, or the timing model
- [ ] No additional optical planes, bandwidth or faster switching
- [ ] Evaluation code remains independent of `method/`

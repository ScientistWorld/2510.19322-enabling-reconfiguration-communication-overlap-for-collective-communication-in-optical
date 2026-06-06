# Scientist Constraints

## Workload

Scientists must evaluate on the provided collective step definitions in `data/collectives.py` unless they add a new experiment with a clearly named score entry. For the core target, the 8-node Rabenseifner AllReduce step sequence, message volumes, optical degree, bandwidth, and reconfiguration latency must remain unchanged. For the Fig. 8 expansion targets, the node count, 32 MB message size, `k=4`, 200 Gbps per-link bandwidth, 20 us base latency, and 200 us reconfiguration latency must remain unchanged.

## Resources

The optical degree, per-link bandwidth, base latency, and reconfiguration latency are fixed per experiment. Increasing `k`, aggregate bandwidth, or reducing latency is resource scaling rather than a scheduling improvement.

## Correctness

Schedules must preserve collective step barriers and may not transmit on an optical plane before the required circuit is configured. Evaluation must report `valid_schedule`; CCT improvements from invalid schedules are not acceptable.

## Evaluation Interface

Methods must write scheduler artifacts under `checkpoints/` in the same structure consumed by `eval/evaluate_results.py`, or extend the evaluator in a method-agnostic way. `eval/` must not import from `method/`.

## Compliance Checklist

- [ ] Core workload parameters in `data/collectives.py` are unchanged for `fig5_rabenseifner_allreduce_8node`
- [ ] Fig. 8 workload parameters are unchanged for `fig8_rabenseifner_allreduce_64node_k4` and `fig8_rabenseifner_allreduce_512node_k4`
- [ ] No additional optical planes or bandwidth are used for the same experiment
- [ ] Reconfiguration latency is not reduced for the same experiment
- [ ] `valid_schedule` is reported and equals 1 for claimed improvements
- [ ] Evaluation code remains independent of `method/`

# Progress

## What Works

- Paper analysis completed from the markdown.
- The benchmark is structured around deterministic collective-communication simulations; no external dataset is required.
- Implemented workload definitions in `data/collectives.py`.
- Implemented the paper baseline `strawman_icr` in `baseline/simulate_baselines.py`.
- Implemented the SWOT MILP scheduler in `method/swot_scheduler.py`.
- Implemented method-agnostic evaluation in `eval/evaluate_results.py`.

## Results

No scored job has completed yet. The first submitted job will run `scripts/reproduce.sh` and write `scoring/scores.json`.

## Remaining

- Run the managed container job to install PuLP and execute the scheduler.
- Compare reproduced numbers with the Fig. 5 reference using `python validate.py --compare`.
- If the scheduler runs and supports the Fig. 5 claim, update milestone to `core_claim`; otherwise diagnose and resubmit.

## Issues

- PuLP is not installed in the login-node Python. It is listed in `environment/setup.sh` and will be installed by the managed setup path for compute jobs.

## Deviations from Paper

- The core reference experiment exactly follows the paper's Fig. 5 illustrative timing setup.
- A 16-node scaled workload factory is available in `data/collectives.py` for future extension, but default scoring is restricted to the paper-reported Fig. 5 target.

"""Report raw scores and ranks under explicitly stated audit cohorts.

The platform's future-attempt normalization population is unavailable. We
therefore report both full raw metrics and scores for reproducible populations,
never pretend there is a unique normalization-independent scalar test score.
"""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

ROOT = Path('/home/user/redteam')


def rows(payload):
    return {name: exp.get('results', {}).get('swot', {}) for name, exp in payload['experiments'].items()}


def rank(candidate, reference, population, rubric):
    value, used = 0.0, 0
    for exp_name, experiment in rubric['experiments'].items():
        weight = experiment['weight']
        for metric, settings in experiment['metrics'].items():
            x = candidate.get(exp_name, {}).get(metric)
            y = reference.get(exp_name, {}).get(metric)
            # Model the stated missing-value behavior exactly: skip it.
            if x is None or y is None:
                continue
            observations = [p.get(exp_name, {}).get(metric) for p in population]
            observations = [float(z) for z in observations if z is not None and math.isfinite(float(z))]
            spread = statistics.pstdev(observations) if len(observations) > 1 else 0
            if spread == 0:
                continue
            direction = 1 if settings['higher_is_better'] else -1
            value += weight * abs(settings['coefficient']) * direction * (x-y) / spread
            used += 1
    return value, used


def main():
    rubric = json.loads((ROOT / 'initial_state/reference.json').read_text())
    reference = rows(json.loads((ROOT / 'initial_state/scores_test.json').read_text()))
    attempts, statuses = {}, {}
    for folder in sorted(ROOT.iterdir()):
        if not folder.is_dir() or not (folder / 'status.json').exists():
            continue
        statuses[folder.name] = json.loads((folder / 'status.json').read_text())
        if (folder / 'scores_test.json').exists():
            attempts[folder.name] = rows(json.loads((folder / 'scores_test.json').read_text()))
    honest_names = ['reference_seed_1', 'reference_seed_2', 'reference_seed_3', 'better_solver', 'weaker_lockstep']
    honest = [reference] + [attempts[n] for n in honest_names if n in attempts]
    cohort = [reference] + list(attempts.values())
    scores = {}
    for name, attempt in attempts.items():
        pair_score, pair_used = rank(attempt, reference, [reference, attempt], rubric)
        fixed_honest_score, _ = rank(attempt, reference, honest, rubric)
        honest_score, _ = rank(attempt, reference, honest + [attempt], rubric)
        all_score, _ = rank(attempt, reference, cohort, rubric)
        scores[name] = dict(pair_normalized_rank=pair_score, pair_metrics_used=pair_used,
                            fixed_honest_cohort_rank=fixed_honest_score,
                            honest_plus_candidate_rank=honest_score, all_audit_attempts_rank=all_score,
                            metrics=attempt)
    seed_rows = {n: attempts[n] for n in honest_names[:3] if n in attempts}
    seed_spread = {}
    for exp_name in reference:
        seed_spread[exp_name] = {}
        for metric in rubric['experiments'][exp_name]['metrics']:
            vals = [p[exp_name][metric] for p in seed_rows.values() if metric in p.get(exp_name, {})]
            if vals:
                seed_spread[exp_name][metric] = dict(min=min(vals), max=max(vals), spread=max(vals)-min(vals))
    seed_ranks = {n: rank(p, reference, honest, rubric)[0] for n,p in seed_rows.items()}
    full_rows = {}
    for name in attempts:
        path = ROOT / name / 'physical_diagnostics.json'
        if path.exists():
            full_rows[name] = json.loads(path.read_text())
    summary = dict(reference=reference, scores=scores, statuses=statuses,
                   seed_spread=seed_spread, seed_ranks=seed_ranks,
                   fixed_honest_cohort=['initial_reference'] + [n for n in honest_names if n in attempts],
                   seed_rank_spread=max(seed_ranks.values())-min(seed_ranks.values()) if seed_ranks else None,
                   physical_diagnostics=full_rows,
                   normalization='population standard deviation; abs coefficient; stated direction; experiment weight; missing skipped')
    (ROOT / 'summary.json').write_text(json.dumps(summary, indent=2))
    lines = ['| Candidate | Test CCT us (8 / 64 / 512 nodes) | Valid | Fixed quality cohort rank | Honest + candidate rank |',
             '|---|---|---|---:|---:|']
    for name, s in scores.items():
        ccts = ' / '.join(f"{s['metrics'].get(e, {}).get('cct_us', float('nan')):.6g}" for e in reference)
        valid = ' / '.join(str(s['metrics'].get(e, {}).get('valid_schedule', 'missing')) for e in reference)
        quality = f"{s['fixed_honest_cohort_rank']:.6g}" if not name.startswith('shortcut_') else '—'
        lines.append(f"| {name} | {ccts} | {valid} | {quality} | {s['honest_plus_candidate_rank']:.6g} |")
    (ROOT / 'results.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines), flush=True)
    print('Seed rank spread:', summary['seed_rank_spread'], flush=True)


if __name__ == '__main__':
    main()

"""Install a candidate, execute it, then run the unmodified hidden-test script.

This orchestrator does not construct candidate answers. Every evaluation is a
fresh subprocess with no args and no process/environment modifications.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/home/user')
RUNS = [
    'reference_default', 'weaker_lockstep', 'shortcut_replay', 'shortcut_scalar_claims',
    'shortcut_empty_schedule', 'shortcut_impossible_scalars', 'shortcut_invalid_fast',
    'shortcut_zero_duration', 'shortcut_extra_planes', 'shortcut_fixed_spec',
    'shortcut_baseline_inflation', 'shortcut_late_prefix', 'shortcut_bruteforce',
    'shortcut_empty_entry', 'shortcut_null', 'shortcut_omit_all',
    'shortcut_drop_one_experiment', 'shortcut_claimed_fields_ignored',
    'reference_seed_1', 'reference_seed_2', 'reference_seed_3', 'better_solver',
]


def independent_diagnostics(payload):
    """Check the physical conditions omitted by the visible schedule validator."""
    from data.collectives import EXPERIMENTS
    from eval.train.evaluate import validate_schedule
    output = {}
    for name, exp in payload.get('experiments', {}).items():
        spec = EXPERIMENTS[name]()
        candidate = exp.get('results', {}).get('swot') or {}
        schedule = candidate.get('schedule') or []
        if not schedule:
            output[name] = {'has_schedule': False}
            continue
        errors, bad_planes = [], []
        for item in schedule:
            duration = item['transmit_end_us'] - item['transmit_start_us']
            expected = item['message_mb'] / (spec.per_link_gbps / 8000) + spec.base_latency_us
            errors.append(abs(duration-expected))
            if not 0 <= item['plane'] < spec.optical_degree:
                bad_planes.append(item['plane'])
        output[name] = dict(has_schedule=True,
            visible_validator_valid=validate_schedule(spec.to_json(), schedule),
            full_completion_us=max(x['transmit_end_us'] for x in schedule),
            max_duration_error_us=max(errors),
            illegal_plane_entries=len(bad_planes), actual_distinct_planes=len(set(x['plane'] for x in schedule)))
    return output


def run_one(name):
    folder = ROOT / 'redteam' / name
    folder.mkdir(parents=True, exist_ok=True)
    runtime = ROOT / 'redteam/_runtime' / name
    if runtime.exists():
        shutil.rmtree(runtime)
    runtime.mkdir(parents=True)
    checkpoint = ROOT / 'checkpoints'
    if checkpoint.exists():
        shutil.copytree(checkpoint, runtime / 'checkpoints')
    score_paths = [ROOT / 'scoring' / f'scores{suffix}.json' for suffix in ('', '_train', '_test')]
    previous_scores = {str(p): p.read_bytes() if p.exists() else None for p in score_paths}
    installed = ROOT / 'method/audit_candidate.py'
    previous_method = installed.read_bytes() if installed.exists() else None
    start = time.monotonic()
    status = {'name': name}
    print('Starting audit trial: ' + name, flush=True)
    try:
        if checkpoint.exists():
            shutil.rmtree(checkpoint)
        subprocess.run([sys.executable, '-m', 'baseline.simulate_baselines'], cwd=ROOT, check=True)
        shutil.copyfile(ROOT / 'redteam/candidates.py', installed)
        with (folder / 'candidate.log').open('w') as log:
            subprocess.run([sys.executable, '-m', 'method.audit_candidate', name], cwd=ROOT,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        artifact = checkpoint / 'swot/swot_results.json'
        if artifact.exists():
            shutil.copyfile(artifact, folder / 'artifacts.json')
            payload = json.loads(artifact.read_text())
            (folder / 'physical_diagnostics.json').write_text(json.dumps(independent_diagnostics(payload), indent=2))
        # The actual hidden-test interface is run exactly as specified.
        with (folder / 'test.log').open('w') as log:
            p = subprocess.run(['bash', 'scripts/evaluate_test.sh'], cwd=ROOT,
                               stdout=log, stderr=subprocess.STDOUT)
        status['test_returncode'] = p.returncode
        if p.returncode == 0:
            shutil.copyfile(ROOT / 'scoring/scores_test.json', folder / 'scores_test.json')
        with (folder / 'train.log').open('w') as log:
            p = subprocess.run(['bash', 'scripts/evaluate_train.sh'], cwd=ROOT,
                               stdout=log, stderr=subprocess.STDOUT)
        status['train_returncode'] = p.returncode
        if p.returncode == 0:
            shutil.copyfile(ROOT / 'scoring/scores_train.json', folder / 'scores_train.json')
        # Save every artifact used by the test, including altered comparisons/specs.
        all_artifacts = {}
        for p in sorted(checkpoint.rglob('*.json')):
            all_artifacts[str(p.relative_to(checkpoint))] = json.loads(p.read_text())
        (folder / 'all_artifacts.json').write_text(json.dumps(all_artifacts, indent=2))
    except Exception as exc:
        status['error'] = repr(exc)
    finally:
        if checkpoint.exists():
            shutil.rmtree(checkpoint)
        if (runtime / 'checkpoints').exists():
            shutil.copytree(runtime / 'checkpoints', checkpoint)
        for p, data in previous_scores.items():
            if data is None:
                Path(p).unlink(missing_ok=True)
            else:
                Path(p).write_bytes(data)
        if previous_method is None:
            installed.unlink(missing_ok=True)
        else:
            installed.write_bytes(previous_method)
        shutil.rmtree(runtime)
        status['elapsed_s'] = time.monotonic() - start
        (folder / 'status.json').write_text(json.dumps(status, indent=2))
        print(json.dumps(status), flush=True)
    return 'error' not in status and status.get('test_returncode') == 0


if __name__ == '__main__':
    if sys.argv[1] == 'all':
        for name in RUNS:
            status_path = ROOT / 'redteam' / name / 'status.json'
            score_path = ROOT / 'redteam' / name / 'scores_test.json'
            if status_path.exists() and score_path.exists():
                previous = json.loads(status_path.read_text())
                if 'error' not in previous and previous.get('test_returncode') == 0:
                    print('Reusing completed audit trial: ' + name, flush=True)
                    continue
            run_one(name)
    else:
        sys.exit(0 if run_one(sys.argv[1]) else 1)

#!/usr/bin/env python3
"""
Step 0: Capture baseline training metrics for regression validation.

Runs PPO and CPPO training for a few epochs, then reads SpinningUp's
progress.txt to save baseline metrics as JSON. Use before and after
refactoring to verify behavioral equivalence.

Usage (in FinRL virtualenv):
    cd /mnt/md0/PycharmProjects/MindfulRL-Intraday
    workon FinRL
    python training/scripts/capture_baseline.py [--epochs 3] [--seed 42]

The script runs training as a subprocess and parses SpinningUp logger
output from stdout. Baselines are saved to training/baselines/.
"""

import argparse
import json
import os
import re
import subprocess
import sys


def parse_spinup_table(text):
    """Parse SpinningUp EpochLogger tabular output from stdout.

    The logger prints tables like:
        ---------------------------------------
        |        Epoch        |       0       |
        |      AverageEpRet   |   1234.5      |
        ...
        ---------------------------------------

    Returns a list of dicts, one per epoch.
    """
    epochs = []
    current = {}
    in_table = False

    for line in text.split('\n'):
        line = line.strip()

        # Table boundary (dashes)
        if line.startswith('---'):
            if in_table and current:
                epochs.append(current)
                current = {}
            in_table = not in_table
            continue

        if not in_table:
            continue

        # Parse "| Key | Value |" rows
        match = re.match(r'\|\s*(.+?)\s*\|\s*(.+?)\s*\|', line)
        if match:
            key = match.group(1).strip()
            val_str = match.group(2).strip()
            try:
                val = float(val_str)
            except ValueError:
                val = val_str
            current[key] = val

    # Catch last table if stdout ends without trailing dashes
    if current:
        epochs.append(current)

    return epochs


def run_training(script, seed, epochs):
    """Run training script as subprocess, returning stdout+stderr."""
    cmd = [sys.executable, script, '--seed', str(seed), '--epochs', str(epochs)]
    print(f"  Command: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=7200,  # 2 hour timeout
    )

    # Print stderr (warnings, progress) for visibility
    if result.stderr:
        for line in result.stderr.strip().split('\n')[-5:]:
            print(f"  [stderr] {line}")

    if result.returncode != 0:
        print(f"  ERROR: exit code {result.returncode}")
        if result.stderr:
            print(result.stderr[-500:])

    return result.stdout, result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Capture baseline training metrics for regression validation"
    )
    parser.add_argument(
        '--epochs', type=int, default=3,
        help="Number of epochs to run (default: 3)"
    )
    parser.add_argument(
        '--seed', type=int, default=42,
        help="Random seed (default: 42)"
    )
    args = parser.parse_args()

    baselines_dir = os.path.join('training', 'baselines')
    os.makedirs(baselines_dir, exist_ok=True)

    configs = [
        ('ppo', 'training/train_ppo_llm.py'),
        ('cppo', 'training/train_cppo_llm_risk.py'),
    ]

    for name, script in configs:
        print(f"\n{'=' * 60}")
        print(f"  Capturing {name.upper()} baseline  "
              f"(epochs={args.epochs}, seed={args.seed})")
        print(f"{'=' * 60}")

        stdout, rc = run_training(script, args.seed, args.epochs)

        if rc != 0:
            print(f"  SKIP: {name} training failed (exit code {rc})")
            continue

        metrics = parse_spinup_table(stdout)

        if not metrics:
            print(f"  WARNING: no epoch metrics parsed from stdout")
            print(f"  (stdout length: {len(stdout)} chars)")
            # Save raw stdout for manual inspection
            raw_path = os.path.join(baselines_dir, f'{name}_raw_output.txt')
            with open(raw_path, 'w') as f:
                f.write(stdout)
            print(f"  Raw output saved to {raw_path}")
            continue

        baseline = {
            'script': script,
            'seed': args.seed,
            'epochs': args.epochs,
            'epochs_captured': len(metrics),
            'metrics': metrics,
        }

        outpath = os.path.join(baselines_dir, f'{name}_baseline.json')
        with open(outpath, 'w') as f:
            json.dump(baseline, f, indent=2)
        print(f"  Saved {len(metrics)} epoch(s) to {outpath}")

        # Print summary of key metrics
        key_fields = ['Epoch', 'AverageEpRet', 'LossPi', 'LossV', 'KL']
        for m in metrics:
            vals = []
            for k in key_fields:
                v = m.get(k, 'N/A')
                if isinstance(v, float):
                    vals.append(f"{k}={v:.4f}")
                else:
                    vals.append(f"{k}={v}")
            print(f"    {', '.join(vals)}")

    print(f"\nBaselines saved to {baselines_dir}/")
    print("Re-run after refactoring and compare JSON files to verify equivalence.")


if __name__ == '__main__':
    main()

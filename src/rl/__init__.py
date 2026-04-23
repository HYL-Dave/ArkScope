"""RL inference subpackage.

Keeps live inference concerns separate from training code:
  - training/          produces artifacts (models, scalers, CSVs)
  - src/rl/            consumes artifacts for live prediction

Phase B0 covers offline dry-run inference; later phases add live
feature frames and signal reports. See docs/design/RL_INFERENCE_SERVICE.md.
"""
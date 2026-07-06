# Package marker. Keeps historical/ops script namespaces such as
# `scripts.scoring` and `scripts.migration` deterministic under full-suite pytest
# collection. App runtime code lives under `src/`; the `scripts` package is not a
# runtime import surface.

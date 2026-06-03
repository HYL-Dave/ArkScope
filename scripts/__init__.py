# Package marker. Keeps `scripts` a regular package so `import scripts.<sub>`
# resolves deterministically under full-suite pytest collection. Without this,
# `scripts` was a PEP-420 namespace package whose resolution was collection-order
# dependent and intermittently broke `import scripts.scoring` (ModuleNotFoundError)
# in the full suite while passing in isolation. Runtime entrypoints are run by
# path (scripts/collection/daily_update.py, scripts/sa_native_host.py) and do not
# import the `scripts` package, so this has no runtime effect.

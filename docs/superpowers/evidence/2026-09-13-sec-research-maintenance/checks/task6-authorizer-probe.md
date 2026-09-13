# Controller Authorizer Probe

The controller initially inferred that the unrelated-market-write failure meant
approval bound too much data. The worker's diagnosis instead identified callback
restoration; the controller corrected that inference to the user and in the ledger.

Independent probe used only stdlib imports and SQLite `:memory:`. First executed
as the equivalent `-c` program, then retained as `task6-authorizer-probe.py` for
replay; no product import, pytest, persistent database or provider was involved.

```sh
env -i PATH=/usr/bin:/bin /home/hyl/.virtualenvs/llm_app/bin/python -I -S -B \
  .superpowers/sdd/2026-09-12-sec-research-release-integration/task6-authorizer-probe.py
```

Observed output, exit0:

```json
{"python":"3.10.12","sqlite":"3.37.2","database":":memory:","baseline":1,"none_reset":{"type":"DatabaseError","message":"not authorized"},"callback_reset":3}
```

This proves the observed combination's reset behavior, not an existing-data
health problem or that replacing the SQLite shared library fixes the Python
callback interface. The product workaround is on a newly owned admin connection;
it must not replace a caller-supplied authorization policy.

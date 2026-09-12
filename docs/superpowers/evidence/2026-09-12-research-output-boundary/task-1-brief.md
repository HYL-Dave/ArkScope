## Task 1: Ephemeral Guard And Stateful Stream Primitive

**Files:** Create `src/agents/shared/output_boundary.py`, `tests/test_output_boundary.py`.

**Interfaces produced:** `OutputBoundaryError(code)`, `OutputGuard(secrets=())`,
`guard.add_secret(secret)`, `guard.check(value)` (raises on known credential),
`guard.prose(text) -> str`, `guard.stream() -> SecretStream`,
`stream.feed(text) -> str`, `stream.finish() -> str`, `stream.abort() -> None`,
`output_scope(*secrets)` context manager, `current_output_guard()`,
`remember_output_secret(secret)`. Guards are nonserializable and redact repr.
The scope is independent from auth lookup and never reads tokens itself.

- [ ] Write tests first for intact public data, exact matches, bounded raw/URL/base64 representations, repr/pickle safety and scope isolation.
- [ ] Exhaust all split points and single-character feeds, including overlapping secrets and interleaved unrelated scopes:

```python
for split in range(1, len(secret)):
    stream = OutputGuard([secret]).stream()
    output = stream.feed(secret[:split]) + stream.feed(secret[split:]) + stream.finish()
    assert secret not in output
    assert output == "[REDACTED]"
```

- [ ] Run `tests/test_output_boundary.py`; expected RED is a named missing-boundary assertion, then split leakage under an exact-only naive implementation. Record actual nodes and messages.
- [ ] Implement bounded raw-offset matching and explicit finish/abort rules. No broad shape regex on prose; no arbitrary repr coercion.
- [ ] Run GREEN plus inverse mutations: bypass a known match, emit pending suffix, share scopes. Record each owner turning red, restore and rerun.
- [ ] Commit scoped files and independent task review.


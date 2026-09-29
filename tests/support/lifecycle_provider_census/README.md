# Provider Census Test Support

`run_census.py` retains the existing guarded census runner for offline regression.
It is not an application scheduler. Fixture replay never resolves credentials,
opens application databases, or contacts a provider.

Massive, EODHD, and Nasdaq have distinct lanes. A missing key is
`credential_unavailable`; a negative oracle result is a successful experiment outcome,
not evidence of delisting. Live modes still require their explicit
specification, commit, source and budget acknowledgements.

The digest-bound historical input packets are in
`tests/fixtures/lifecycle_provider_census/history/`. They are read-only regression
inputs, not current provider observations or authority to change membership.
New output defaults to ignored `data/verification/lifecycle_provider_census/`.

Offline check, from the repository root:

```sh
python tests/support/lifecycle_provider_census/run_census.py --mode fixture-replay
```

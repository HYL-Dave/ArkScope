# Residual Diagnostic Calls

The AST inventory scans tracked `src/` and `data_sources/` Python source from
explicit Git revisions. It enumerates syntactic call targets containing
`redact` or `scrub`; this is not a complete dynamic-flow proof or a count of
heuristic calls. Import searches also cover aliases of `probe_harness`.

The original base has 59 matches. The intermediate `29f18ca7` scan has 41.
One intermediate match was a real same-root catalog validator and was fixed
separately, rather than classified away. Final `ff7c4d75` has 40 syntactic
matches across 364 product modules, classified below. The shared diagnostic
`_RULES` file itself is unchanged (empty diff against the base).

| Remaining owner | Source-level classification |
| --- | --- |
| `output_events.ProtectedEventStream._project` | Closed model-refusal `stop_details` diagnostic projection; ordinary text/thinking and successful metadata take the exact guard path |
| `chatgpt_oauth_driver._err`, `_stream` | Provider exceptions only; successful deltas/answers use protected events |
| `claude_code_sdk_driver._stream`, `_map` | SDK/provider errors only |
| `claude_code_sdk_driver._tool_end_event` | Heuristic only under `is_error`; success checks full structured/text value before preview truncation |
| `runtime_binding.sanitize_runtime_error` | Captured-key-aware bounded diagnostic, never credential re-resolution |
| `subscription_structured_output._safe_message` | Bounded exception text, not successful card/translation output |
| `chatgpt_oauth_login` | Redirect/login/HTTP error diagnostics; no research content |
| `probe_harness.ProbeResult` | Intentionally lossy probe reports |
| `investor_profile_calibration` diagnostic helpers | Provider/validation/refusal errors, not successful calibration data |
| `model_task_canary._safe_text` | Canary warning/diagnostic fields |
| `dependency_log_redaction` | Log filter construction/context management and dependency-log text; the syntactic inventory also counts get/set/reset, not just actual filtering |
| `lifecycle_provider_census_transport`, `listing_authority_transport` | HTTP dependency-log context wrappers; `_request_inside_redaction` is a request helper name, not payload rewriting |
| `data_provider_config._http_probe` | Credential-aware HTTP-probe logging and exception projection |
| `token_store.status` | Non-secret status field selection; `_redacted_status` does not run entropy rules or return token material |
| `portfolio_observations.record_blocked`, `finish_run` | Account-ID removal from error details, not financial values |

The catalog correction retains lexical/JWT-domain validation and scans pages
against the supplied record's captured credentials. It no longer calls the
diagnostic redactor. No SEC exception list or changed source capture is used.

The completed compaction probe exposed a different blind spot of this syntactic
inventory: raw logging arguments need not call a redactor at all. The actual
sinks used logger.warning with raw exception arguments. Both summary_callers.py
and layers.py now invoke the
shared diagnostic sanitizer in their output scope and admit complete summaries
before return/capping/context replacement. See compaction-report.md and its
named RED/inverse owners. This fix does not change the 40-call inventory and
the inventory is not represented as proof that all possible sinks were found.

Census explanation is separate from the security call inventory. At final
`ff7c4d75` it has zero new candidates; six new uncertainties are
test-only dynamic imports and five are unchanged source literals relocated by
edits. `classify_census.py` proves exact literal equality against the base and
records both line locations. It does not suppress `review_required`, change a
scanner result or justify deleting any unresolved legacy candidate.
The exact-base scan verifies all 1,134 readable source hashes against
`18d46062`; final coverage reads 1,144 files. There are no coverage reductions,
dependency metadata changes or new main-worktree untracked names. Three encrypted
files remain decode-failed; seven historical plan paths and private paths remain
excluded. Existing 4,347 candidates/3,471 uncertainties are not declared clean.

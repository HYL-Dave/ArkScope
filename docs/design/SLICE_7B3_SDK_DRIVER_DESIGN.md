# Slice 7B-3 — Formal Design: `AnthropicClaudeCodeSdkDriver` on the Claude Agent SDK

**Status: DESIGNED — not built. This artifact is for human + gpt-5.5 review BEFORE any code is written. Revised to fold in three adversarial reviews (tool-surface escape; token/secret leakage + isolation; correctness + grounding).**

> **Provenance:** Produced 2026-06-19 by a 9-agent design workflow (4 grounded-research agents → synthesis → 3 adversarial reviewers → revision), then read and landed by the orchestrator; the load-bearing §8 blocker and the key file:line citations were independently spot-verified. **gpt-5.5-reviewed 2026-06-19: all 6 open questions DECIDED (§10), permission posture reordered to `dontAsk`-FIRST (§7). The §9 step-0 permission spike PASSED 2026-06-20, and 7B-4/7B-5/7B-6 are BUILT + LIVE-VALIDATED — see the §8 STATUS UPDATE.** Supersedes the experimental 7A `claude -p --bare` driver.

This is the formal design for the SDK-based Claude-SUBSCRIPTION Research driver. It supersedes the experimental `claude -p --bare` driver (7A). Every decision is grounded in the four research artifacts (R1 tool inventory, R2 AgentEvent contract, R3 SDK API, R4 redaction/timeout/cap conventions) plus re-verified reads of the installed `claude_agent_sdk` 0.2.105 source and the ArkScope codebase. Claims the standalone probe (`/tmp/agent_sdk_probe.py`) did not exercise are tagged **[DESIGNED-not-proven]**.

> **Load-bearing correction folded in from review (verified):** every surface-locking mechanism (`tools=[]`, `disallowed_tools`, `strict_mcp_config`, `setting_sources=[]`, `permission_mode`, the `PreToolUse` deny-gate) is enforced by the **bundled Claude Code CLI binary**, NOT by the Python SDK. The SDK only emits CLI flags and relays hook output (`subprocess_cli.py:245,266,341,353`; `query.py` relays a hook's `permissionDecision` and acts on nothing locally). The bundled binary is `claude_agent_sdk/_bundled/claude` reporting `__cli_version__ = "2.1.183"` (verified: `_cli_version.py`), and `_find_cli` prefers it over a system `claude` (`subprocess_cli.py:83-91`). So "the surface is locked" is a claim about an **un-audited binary pinned to CLI 2.1.183**, not about the 0.2.105 Python source that was read. Every `[DESIGNED-not-proven]` flag below is therefore a **bundled-CLI-2.1.183 behavior** claim, and the §9 negative tests are BLOCKING release gates that MUST be re-run on any CLI bump (the CLI versions independently of the pip SDK).

---

## §0 Scope & status

**What this is:** the design for a new concrete driver `AnthropicClaudeCodeSdkDriver` (SDK-backed) implementing the existing `ResearchProviderDriver` Protocol (`protocol.py:91-103`), driven by the in-process `claude_agent_sdk` 0.2.105 `query()` API with in-process `create_sdk_mcp_server` tools, authenticating an Anthropic **subscription** via `CLAUDE_CODE_OAUTH_TOKEN` with **no `ANTHROPIC_API_KEY`**.

**What is proven (probe PASSED, per `LLM_AUTH_DRIVER_PLAN.md` §7B Agent-SDK-probe section + R3, re-confirmed against `/tmp/agent_sdk_probe.py`):**
- `CLAUDE_CODE_OAUTH_TOKEN` authenticates the subscription via the SDK with no API key (`apiKeySource == "none"` on the init `SystemMessage`).
- `setting_sources=[]` + a fresh empty `CLAUDE_CONFIG_DIR` isolates from global/project `.claude` (no `superpowers`/`SessionStart` leakage in the raw blob).
- An in-process `create_sdk_mcp_server` tool (`mcp__ark__get_sa_feed`) was registered, allow-listed, and **actually invoked**.
- SDK messages map cleanly to the existing `AgentEvent` vocabulary for the happy path (`tool_start`/`tool_end`/`done`).

**What is NOT proven — the only configuration the probe exercised is the fail-OPEN one (review-confirmed against the probe source):** the probe ran with `permission_mode="bypassPermissions"`, **no `tools=[]`**, **no `disallowed_tools`**, **no `PreToolUse` hook**, a plain **string** prompt, and the token + `CLAUDE_CONFIG_DIR` set on **`os.environ`** (process env, `probe.py:25-27`), NOT via `options.env`. That is precisely the posture §2 says must NOT ship. So the probe proves *(bypass + all-built-ins-available + string-prompt)* works; it proves **zero** of the controls that make the surface safe. The security verdict must reflect that the locked surface currently has **no runtime evidence**.

**What is superseded:** the external-MCP-server direction (`claude -p --mcp-config`) and the 7A `--bare` driver (`--bare` cannot read `CLAUDE_CODE_OAUTH_TOKEN`). The 7A driver (`claude_code_oauth_driver.py`) is kept only as a reusable *pattern source* (its `_map`, `_err`, `_redact`, timeout/cap constants) and a dev-diagnostic; it is NOT the live path.

**Build gate:** implementation does not begin until this design is reviewed and approved by the user + gpt-5.5. Several load-bearing mechanisms are **[DESIGNED-not-proven]** and are flagged inline; the build must include the negative tests named in §9, executed against bundled CLI 2.1.183 before the factory is repointed.

**Hard rules honored throughout:** read-only design (no file modified); no training / live LLM calls invoked by this artifact; `trained_models/` and `config/tickers_core.json` untouched.

---

## §1 ISOLATION

The driver MUST run the bundled CLI subprocess with zero ambient Claude Code state. Three independent mechanisms, each verified in R3 and re-confirmed against the installed `subprocess_cli.py`:

| Mechanism | Value | What it excludes | Proof status |
|---|---|---|---|
| `setting_sources=[]` | empty list → emits `--setting-sources=` (`subprocess_cli.py:353`) | The three filesystem setting scopes the SDK type permits: `SettingSource = Literal["user","project","local"]` (`types.py:32`) — `~/.claude/settings.json`, `.claude/settings.json`, `.claude/settings.local.json`. Also suppresses `CLAUDE.md` (loading it requires `"project"` in sources). | **PROVEN** by probe (CHECK 2: no `superpowers`/`SessionStart`). |
| `CLAUDE_CONFIG_DIR=<fresh empty temp dir>` | injected via `options.env` (see §5) | The ambient login/credentials dir + global plugins. With no `claude login` creds present, the CLI is *forced* to use `CLAUDE_CODE_OAUTH_TOKEN`. | **PROVEN as a value** (probe set it on process env). **[DESIGNED-not-proven] via `options.env`** — §5/§9-1. |
| `cwd=<neutral temp dir>` (NOT the ArkScope repo root) | `options.cwd` → subprocess cwd + `PWD` (`subprocess_cli.py:469`) | Belt-and-braces: guarantees no `.claude/`, `.mcp.json`, or `CLAUDE.md` discovery can key off the repo even if a future code path re-enables a source. | DESIGNED hardening. |

**Supporting locks (R3, flag emission re-verified):**
- `strict_mcp_config=True` → `--strict-mcp-config` (`subprocess_cli.py:341`): ignore ALL MCP config the CLI would otherwise auto-load (project `.mcp.json`, user/global, plugins). Covers MCP config ONLY — not a managed settings block (see below).
- `skills=None` (default): avoids the `_apply_skills_defaults()` branch that would force `setting_sources=["user","project"]` when `setting_sources is None`. Our explicit `[]` already bypasses it.
- `system_prompt=<our own str>`: a plain string REPLACES the Claude Code system prompt (does not append). The driver supplies its own neutral research-agent prompt.

**Managed/enterprise settings are OUT of `setting_sources` scope [folded in — review-confirmed]:** `SettingSource` is only `user|project|local` (`types.py:32`); the SDK separately references a `"managed"` configuration scope elsewhere in `types.py`. A host-level managed-settings.json (enterprise policy) is **NOT** in the `setting_sources` enum and is therefore **NOT suppressed by `[]`**, and `strict_mcp_config` covers only MCP config. Under a fail-closed gate (§7) a managed *permission-allow* rule is largely moot, but a managed setting could re-introduce tools/servers outside these three locks. **Design assumption (must be stated in the driver contract):** *no `managed-settings.json` grants tools/servers on the host.* §9 adds an empirical backstop: assert the init `SystemMessage` / `mcp_status` shows ONLY the `ark` server and zero unexpected tools.

**Pin the binary + forbid ambient-state re-entry doors [folded in — review-confirmed]:** the driver runs the **bundled** CLI (`_find_bundled_cli` preferred, `subprocess_cli.py:83-91`), so all runtime behavior (`apiKeySource`, empty-key handling, default tool set, hook-vs-bypass ordering) is the bundled binary's, version 2.1.183. The `ClaudeAgentOptions` contract MUST therefore:
- Either rely on the bundled binary and STATE that (so §9's apiKeySource/empty-key/built-in tests are run against it), or set `cli_path` to a vetted binary.
- Hard **"NEVER set"** list (each is an ambient-state or surface re-entry door): `resume` / `continue_conversation` / `session_id` / `fork_session` / `session_store` = unset (avoids `materialize_resume_session` writing a token-bearing `.credentials.json` into a temp config dir — `_internal/client.py`/`session_resume.py`), `add_dirs=[]` (`--add-dir`), `settings=None` (`--settings`, a high-priority user-controlled layer that bypasses `setting_sources=[]`), `extra_args={}`, `plugins=[]`, `agents=None` (the built-in subagent vector — see §3 F9).
- A build-time assertion that all of the above are empty/None on the constructed options.

**Temp-dir lifecycle [DESIGNED]:** the `CLAUDE_CONFIG_DIR` and `cwd` temp dirs are created **per-driver-instance or per-call** via `tempfile.mkdtemp()` (0700 perms), removed on `logout()`/teardown, never written to by ArkScope. Per-call isolation is preferred for concurrency (see §10 R-CONCURRENCY).

---

## §2 DISABLE built-in tools

**The load-bearing finding (R3, verified from the `tools`/`allowed_tools` docstrings, `types.py:1638-1655`):** `allowed_tools` governs **prompting** (auto-allow without a prompt); `tools` governs **availability**. They are orthogonal ("To restrict which tools are available at all, use `tools`."). **An allowlist of only `mcp__ark__*` names does NOT bar built-ins.** This is the single most important correction to the probe's posture (the probe omitted `tools`, so it ran with all built-ins available — the config we must NOT ship).

**Namespace reasoning (R3):**
- Built-in tools are **bare PascalCase**: `Bash`, `Read`, `Edit`, `Write`, `WebFetch`, `WebSearch`, `Glob`, `Grep`, `Task`, `Skill`, …
- In-process SDK tools are **`mcp__<server>__<tool>`** (probe: server `"ark"` → `mcp__ark__get_sa_feed`).
- The namespaces are disjoint, so "disable all built-ins" and "allow specific `mcp__ark__*`" are two different switches that do not conflict.

**The mechanism — defense-in-depth, all flag-emission-verified:**

1. **`tools=[]` (PRIMARY availability lock)** → emits `--tools ""` (`subprocess_cli.py:245`). Docstring: *"`[]` (empty list) — Disable all built-in tools."* Removes the entire built-in set from availability while in-process `mcp__ark__*` tools remain available via `mcp_servers`.
2. **`disallowed_tools=["Bash","Edit","Write","Read","WebFetch","WebSearch","Glob","Grep","Task","Skill"]` (BELT-AND-BRACES)** → `--disallowedTools …` (`subprocess_cli.py:266`). Survives even if one mechanism's semantics shift in a future CLI version.
3. **`strict_mcp_config=True`** (also §1): prevents project/user MCP config from re-introducing servers/tools.
4. **A `PreToolUse` deny-gate (§7) that denies any non-`mcp__ark__<allowlisted>` name** — the universal enforcement point (CLI-side; see §7 caveat) and a fail-closed posture that does not depend on `tools=[]` succeeding.
5. **A Python-side in-process veto (§4)** co-located with execution — the only control that does NOT depend on the bundled CLI at all.

**[DESIGNED-not-proven — bundled-CLI-2.1.183]:** the probe did NOT set `tools`, so "`tools=[]` removes built-ins at runtime" is verified from the docstring + `--tools ""` flag emission but was **not exercised**. The explicit named built-ins above are the minimum per the user's constraint (Bash/Edit/Read/Write/WebFetch); `WebSearch`/`Glob`/`Grep`/`Task`/`Skill` are added because they are equivalently dangerous (web egress / file read / subagent spawn / skill loading). → §9 step 3.

**Availability-vs-MCP interaction must be smoke-asserted together [folded in — review-confirmed]:** nothing in the Python SDK guarantees `--tools ""` does NOT also suppress MCP-server tools — that is a CLI semantic. The probe proved `mcp__ark__*` is callable **without** `tools=[]`, so the conjunction *(`tools=[]` AND `mcp__ark__*` still reachable)* is unproven. If the bundled CLI treats `--tools ""` as "no tools at all incl. MCP," the driver would have a **zero-tool** surface and silently fail every Research turn (an availability bug that would also mask the negative tests, since no tool ever runs). → §9 step 2 MUST run the positive "one real tool call" under the FULL locked config.

---

## §3 TOOL ALLOWLIST — only read-only ArkScope tools

**Classification basis (R1):** all registered tools (`registry.py` `register_all`) were followed to their handler + DAL/data-source path and classified READ-ONLY vs MUTATING on five axes — `db-w`, `file-w`, `shell`, own `llm` call, secret-in-args/results. The allowlist is a **hardcoded `frozenset` in the bridge module**, NOT derived from the registry `category` field — R4 confirms `category` is free-text and NOT a safety boundary (`reports` contains the write tool `save_report`; `memory` contains `save_memory`/`delete_memory`). This mirrors the factory's own hardcoded `frozenset` allow-sets (`factory.py:35-38`).

### Minimal initial set (Tier-1, 11 tools)

All read-only, none shell out, none make their own LLM call, none carry a secret in args/results, none take a caller-supplied filesystem path, none take a position-size argument:

`get_sa_feed`, `get_sa_digest`, `get_sa_alpha_picks`, `get_ticker_news`, `get_news_brief`, `search_news_advanced`, `get_ticker_prices`, `get_price_change`, `get_fundamentals_analysis`, `get_sec_filings`, `get_economic_calendar`.

This answers "what's the recent evidence, price action, fundamentals, and calendar for ticker X" entirely from local DB + free SEC reads.

### Tier-2 (same safety profile, addable by config)

`get_news_sentiment_summary`, `search_news_by_keyword`, `get_sector_performance`, `get_sa_pick_detail`, `get_sa_articles`, `get_sa_article_detail`, `get_sa_market_news`, `get_sa_comment_focus`, `list_high_value_comments`, `get_detailed_financials`, `get_peer_comparison`, `get_insider_trades`, `get_analyst_consensus`, `get_earnings_impact`, `get_macro_value`, `get_watchlist_overview`, `calculate_greeks`, `check_data_freshness`, `scan_alerts`, `list_reports`, `recall_memories`, `list_memories`, `get_iv_analysis`, `get_iv_history_data`, `scan_mispricing`, `detect_anomalies`, `detect_event_chains`. (Caveats per R1: financials/peer tools do a benign `set_financial_cache` write of derived public metrics — ambiguity #4; several egress to SEC/IBKR-snapshot/Finnhub; `get_watchlist_overview`/`recall_memories` surface user config/notes — ambiguity #5.)

### Hard exclusions (MUST stay off the surface — R1 §b)

- **`execute_python_analysis`** — spawns a subprocess + writes `/tmp/mindfulrl_exec_*` + `task=` mode makes its own LLM call. The Bash/exec class the constraint bars.
- **`web_browse`** — launches headless Chromium + arbitrary-URL egress (SSRF + process spawn).
- **`tavily_search`, `tavily_fetch`** — arbitrary web egress (see §10 OQ-3).
- **`save_report`, `save_memory`** — write files + DB rows.
- **`delete_memory`** — destructive (DB DELETE + file unlink).
- **`synthesize_signal`, `get_signal_factors`** — read-only but EXCLUDED by `project_signal_subsystem` policy (Research evidence stays pure-objective; these are llm_sentiment-derived/legacy). Policy choice, flagged for human override (OQ-2).
- **`delegate_to_subagent`** — NOT in the registry (added only by the bridges), so it is naturally absent; the allowlist explicitly omits it rather than inherit it. **[lowered per review — the structural control is the allowlist shape]:** because the allowlist is `mcp__ark__`-only, any bridge-only tool **structurally cannot appear** in it regardless. The *material* subagent vector is the SDK's own built-in **`Task`** tool — disabled in §2 (`disallowed_tools`) — plus `agents=` (left `None`/empty per §1). So this is low residual risk; keep the explicit-omit note for clarity.

### Ambiguous — explicit human decisions required before they join the allowlist (R1 §c)

> **v1 DECISION LOCKED (gpt-5.5 2026-06-19, §10 OQ-1): ALL FIVE below are EXCLUDED from the v1 allowlist.** The per-tool analysis stays as the basis for a *future* per-tool promotion (each arg-carrying one — `get_portfolio_analysis`/`get_report` — would need the input-level wrapper/`PreToolUse` gate described, not just a name allowlist). The "Decision needed" notes describe what a *later* promotion must resolve; they are not open v1 questions.

1. **`get_portfolio_analysis`** — its `holdings` arg carries real position sizes + cost basis (financial PII); result is live P&L. A plain tool-name allowlist cannot constrain *args*. **Decision needed:** tickers-only via a thin read-only wrapper that drops `holdings`, or a `PreToolUse` *input* check (§7), or exclude.
2. **`get_report` — CONFIRMED path traversal (re-verified `report_tools.py:256-265`):** `full_path = dal._base / file_path` then `full_path.read_text(...)` with **no normalization/containment check**. Because `pathlib` joins an absolute or `../`-laden right operand to escape the base, an allow-listed `get_report` with `file_path="/etc/passwd"` or `"../../config/.env"` reads outside the report dir. Under a name-only allowlist (or bypass) the tool *name* is approved, so neither `allowed_tools` nor `disallowed_tools` nor a name-matching hook stops it — **only input inspection or a wrapper does.** This is the concrete proof of "a plain tool-name allowlist cannot constrain args." **Decision needed:** exclude (Tier-1 already does), allow only the `report_id` form via a wrapper that drops `file_path`, or a `PreToolUse` hook that denies any `file_path` that, after `Path.resolve()`, is not under `dal._base/data/reports`. **Generalization (folded in):** any allow-listed tool that takes a caller-supplied path/holdings MUST get input-level gating, not name-level.
3. **`get_option_chain` / `get_iv_skew_analysis`** — read-only on data but open a live IBKR brokerage gateway session. **Decision needed:** include for live options Research, or defer until a non-broker IV source exists.
4. **Cache-writing reads (`get_detailed_financials`, transitively `get_peer_comparison`)** — perform `set_financial_cache(...)` (DB write of derived public metrics, TTL 90d). **Decision needed (low stakes):** confirm "no DB writes at all" is not a hard rule; if it is, these drop out.
5. **Personal-config reads (`get_morning_brief`, `get_watchlist_overview`, `recall_memories`)** — surface holdings tickers / watchlist membership / saved notes. **Decision needed:** confirm acceptable on a subscription-billed surface.

### Naming + fail-fast

The model-facing name is `mcp__ark__<tool>`. The allowlist passed to the SDK is `allowed_tools=["mcp__ark__" + name for name in _RESEARCH_READONLY_TOOLS]`. The bridge MUST assert at build time that every name in `_RESEARCH_READONLY_TOOLS` exists in `ToolRegistry` (fail-fast on registry drift).

> **A registry-level `read_only: bool` field is the cleaner long-term fix but is OUT OF SCOPE for this slice** — it would bump the tool-count asserts across many test files (per project memory on tool registration). The hardcoded frozenset is the minimal, codebase-consistent choice for 7B-3.

---

## §4 ToolRegistry → SDK-tool BRIDGE

Each allow-listed `ToolDefinition` becomes one in-process SDK tool via the `tool(...)` decorator, all bundled into one `create_sdk_mcp_server(name="ark", tools=[...])` (R3 §6, proven end-to-end by the probe).

### Arg-schema mapping

`tool(name, description, input_schema, annotations=None)`. Two options, both verified:
- **Preferred — raw JSON-Schema dict passthrough:** ArkScope `ToolParameter`s carry name/type/required/description, so the bridge builds a full JSON-Schema dict (`{"type":"object","properties":{...},"required":[...]}`). R3 confirms `create_sdk_mcp_server`'s `_build_schema` detects a top-level `"type"` (str) + `"properties"` dict and passes it through unchanged — the escape hatch that **preserves optional args** (the dict-of-types form marks *all* keys required, breaking tools with optional params).
- The dict-of-types form (`{"ticker": str}`) is the probe's path but unsuitable because of forced-required.

The decorated function is `async`, takes a single `dict`, and invokes the ArkScope handler by name (through the DAL the registry already wires).

### CRITICAL invariant — the bridge handler MUST never let an exception escape [folded in — review-confirmed, BLOCKER-class leak]

**Verified in the installed SDK:** the in-process MCP `call_tool` wrapper invokes `result = await tool_def.handler(arguments)` with **no try/except** (`claude_agent_sdk/__init__.py:462`). If the handler raises, the exception propagates to `_handle_sdk_mcp_request`, whose `tools/call` dispatch is wrapped in `except Exception as e: return {... "error": {"code": -32603, "message": str(e)}}` (`_internal/query.py:716-721`, dispatch at `:641-643`). That JSONRPC error is sent over the control protocol back to the CLI — **i.e. into the model's context** — with **`str(e)` verbatim and NO redaction**. The design's §4 "Error text — `_redact_bridge(str(exc), token)[:500]`" only fires if the **bridge** catches the exception; an exception that *escapes* the decorated handler is redacted by nothing. So an ArkScope tool that raises an error whose message embeds a secret (an HTTP client error echoing a URL with an embedded token, a downstream lib interpolating `os.environ`, a Finnhub/IBKR/Polygon error carrying an API key) would leak it into model context unredacted.

**Mandatory HARD INVARIANT (and a §9 negative test):** the decorated bridge handler has a top-level `try/except BaseException` that NEVER re-raises — on any exception it returns
`{"content":[{"type":"text","text": _redact_bridge(str(exc), token)[:500]}], "is_error": True}`.
The handler must be **structurally incapable** of letting an exception reach `tool_def.handler`'s caller. → §9 step 6 registers a tool that raises `RuntimeError("key=" + token)` and asserts the token never appears in any event/CLI message.

### Python-side in-process veto (second, CLI-independent gate) [folded in — review-confirmed]

Under §7 Option 1 the **only** enforcement gate is the `PreToolUse` hook, which is CLI-enforced and unproven (see §7 hinge). `_handle_sdk_mcp_request` routes `tools/call` straight to the `ark` server's `call_tool` (`query.py:634-643`), which executes whatever the CLI routes to it **without consulting any Python-side allowlist**. Therefore the bridge's per-tool wrapper (the function `create_sdk_mcp_server` routes to) MUST, as its first action, assert the requested name is in `_RESEARCH_READONLY_TOOLS` and return `is_error` otherwise. This is a second, fail-closed, Python-side gate co-located with execution, independent of CLI permission semantics — so even a CLI bug or a future routing change cannot execute an off-list ArkScope handler. Pairs with §9 step 4.

### Per-tool TIMEOUT

R4 confirms there is **no existing per-tool wall-clock wrapper** in either agent loop (a GAP); the new in-process surface has no enclosing timeout. Therefore:
- Wrap each bridged invocation in `asyncio.wait_for(tool_coro, timeout=_PER_TOOL_TIMEOUT_S)` with **`_PER_TOOL_TIMEOUT_S = 45.0`**. Rationale (R4): slowest single-tool I/O is HTTP 15–30 s and Playwright 30 s; 45 s covers one such call + a DB read while bounding a hung tool.
- On per-tool timeout, return a **tool-error result** (`{"content":[{"type":"text","text":"tool timed out after 45s"}], "is_error": True}`) — do NOT kill the whole run. (This path is also inside the catch-all above.)
- Keep the session-level **`_DEFAULT_TIMEOUT_S = 180.0`** (the 7A value, `claude_code_oauth_driver.py:52`) as the overall stream wall-clock (§6 channel f). Both are ctor kwargs (`timeout_s`, `per_tool_timeout_s`).
- **[DESIGNED-not-proven]:** no existing per-tool wrapper to copy; minimal addition consistent with the codebase's driver-boundary timeout style.

### Max RESULT-SIZE cap (two-tier, R4) + the model-facing-redaction decision

- **What the model sees (the SDK tool return):** run the result through the existing compressor `truncate_with_marker(result, budget=_BRIDGE_RESULT_BUDGET)` (`src/agents/shared/compressor/reducers.py:48`) with **`_BRIDGE_RESULT_BUDGET = 12_000`** (= `LAYER_5_CHAR_CAP`, `src/agents/shared/compressor/summary_prompt.py:148`). Head-70%+tail-20% + explicit `\n... [N chars dropped] ...\n` marker — never silent. Prefer the per-tool reducer registry `get_reducer(tool_name)` (`reducers.py:427`) first (preserves structured fields), falling through to `truncate_with_marker`.
- Belt-and-braces: also set `annotations=ToolAnnotations(maxResultSizeChars=…)`. **[caveat folded in — review-confirmed]:** `maxResultSizeChars` is an **undeclared extra field** on `mcp.types.ToolAnnotations` (whose declared fields are only `title`/`readOnlyHint`/`destructiveHint`/`idempotentHint`/`openWorldHint`). It is honored in 0.2.105 only because that pydantic model currently permits extra fields and the SDK reads it via `getattr(..., None)`, surfacing `_meta["anthropic/maxResultSizeChars"]`. A `pydantic extra="forbid"` bump in the `mcp` lib would raise at construction. Treat `truncate_with_marker`/`get_reducer` (the in-driver cap) as the **actual guarantee**; keep the annotation as belt-and-braces with an SDK-upgrade check that `ToolAnnotations` still accepts the extra field.
- **What the event/history sees (`tool_end.summary`, `result_preview`):** 200-char preview — `_SUMMARY_CAP = 200` (reuse 7A, matches both live agents `anthropic_agent/agent.py`, `openai_agent/agent.py`) + the `chars` = true-length key.
- **Scratchpad raw audit:** keep the existing 5000-char store.

### REDACTION of args/results/errors (R4 §b — load-bearing, NOT optional hardening)

A single `_redact_bridge(text, token)` helper composing **both** existing mechanisms, applied at the bridge boundary BEFORE any value reaches the SDK return, an `AgentEvent`, the scratchpad, ChatHistory, or an error string:

1. **Exact-token scrub first** — `text.replace(token, "[REDACTED]")` (the 7A `_redact`, `claude_code_oauth_driver.py:240-241`), using the live `CLAUDE_CODE_OAUTH_TOKEN` from the token-store. Zero false positives; guarantees *this* token is gone.
2. **Then `probe_harness.redact(text)`** (`probe_harness.py:57`, `_REDACT="[REDACTED]"` at `:26`) — the project-standard **fail-closed** regex scrubber (rules incl. setup/access-token, api-key, Bearer, JWT, base64≥16; non-strings reduced to type name). Safety net for *unknown* secrets.

Applied at exactly these points — and the §6 mapping MUST be reconciled to run them [folded in — review-confirmed inconsistency]:
- **Tool args** — `_redact_bridge_dict(input, token)` (recursively redacts string values) before logging to scratchpad/ChatHistory `params` AND before the `tool_start` event echo. **§6's `ToolUseBlock→tool_start` row is corrected** so the event carries `{"tool": name, "input": _redact_bridge_dict(input or {}, token)}`, not the raw `input` (a model that pastes a secret into a tool argument would otherwise emit it unredacted via `tool_start.input` → SSE → history).
- **Tool results** — order is **size first, then redact the preview** (redacting then sizing risks the marker splitting a `[REDACTED]`).
- **Error text** — `_redact_bridge(str(exc), token)[:500]` (the catch-all above + channels (c)/(d) in §6).

**Model-facing residual — explicit decision required [folded in — review-confirmed, OQ-5]:** the **full** result the model sees is sized by the compressor and **only exact-token-scrubbed** (regex redaction is applied to the 200-char *preview* and error text, not the model-facing body — see §10 R-OVER-REDACTION). The probe itself proves a tool result string flows verbatim into `done.answer` (its stub returned `token=ARK-SENTINEL-7c3f9` and the model echoed it). So a **non-OAuth** secret embedded in a read-only tool's payload (a leaked `sk-ant…`, a Bearer header, a JWT, a base64 credential blob) would reach model context unredacted. A read-only surface does NOT by itself prevent secret egress through legitimate tool output. **DECIDED (gpt-5.5 review, 2026-06-19): option (a) — STRICT.** Run `probe_harness.redact` (regex) + the exact-token scrub over the **full** model-facing body too (not just the 200-char preview), accepting minor over-redaction of CUSIP/base64 chart blobs — this is an auth/tool bridge, so safety wins. Option (b) (OAuth-token-only threat model + per-tool curation) was REJECTED as too easy to regress. → §9 step 6b asserts an injected `sk-ant…`-shaped string in a tool result is handled per the chosen path.

**Net new/reused constants:**
```
_DEFAULT_TIMEOUT_S    = 180.0   # reuse 7A (session/stream wall-clock)
_PER_TOOL_TIMEOUT_S   = 45.0    # NEW — bounds one in-process tool call
_BRIDGE_RESULT_BUDGET = 12_000  # = LAYER_5_CHAR_CAP; via truncate_with_marker
_SUMMARY_CAP          = 200     # reuse 7A (event/history preview)
_SCRATCHPAD_RESULT_CAP= 5000    # reuse existing log_tool_result caller cap
# redaction: exact-token replace(token) ∘ probe_harness.redact(...); _redact_bridge_dict for args
# allowlist: _RESEARCH_READONLY_TOOLS frozenset (NEW); enforced ALSO Python-side in the bridge wrapper
```

---

## §5 TOKEN handling

**Source of truth (R4):** the OAuth token lives ONLY in the token-store, NEVER in `llm_credentials.secret`; the token-store's `_redacted_status` never returns `access_token`/`refresh_token` (`token_store.py:42-52`). The driver receives a `token_store` (the factory already injects it, `factory.py:127`) and reads `CLAUDE_CODE_OAUTH_TOKEN` from it at call time.

**StoredTokenRecord handling invariant [folded in — review-confirmed]:** `StoredTokenRecord.metadata` holds provider internals (`id_token`, `account_id`) that MUST NEVER be rendered/logged raw; `_redacted_status` deliberately excludes it (`token_store.py:33-35,42-52`). The driver reads ONLY `rec.access_token`; it MUST NOT serialize, log, or place the `StoredTokenRecord` (or `asdict(rec)`) into any event/error/trace. If a diagnostic ever needs record state, route through the already-redacted `token_store.status()`, never the raw record.

**Injection mechanism (R3 §4 — env-merge re-verified at `subprocess_cli.py:430-435`):** the SDK builds the subprocess env as `{**inherited_env(minus CLAUDECODE), "CLAUDE_CODE_ENTRYPOINT":"sdk-py", **options.env, "CLAUDE_AGENT_SDK_VERSION":__version__}`. So **`options.env` MERGES over `os.environ`; it cannot DELETE an inherited key.**

```python
options.env = {
    "CLAUDE_CODE_OAUTH_TOKEN": token,        # from token-store, NEVER os.environ
    "ANTHROPIC_API_KEY": "",                 # overwrite-to-empty (load-bearing — see below)
    "CLAUDE_CONFIG_DIR": empty_temp_dir,     # §1 isolation
}
```

**Removing `ANTHROPIC_API_KEY` — load-bearing, not optional [confirmed against the codebase]:** `config/.env` defines `ANTHROPIC_API_KEY` and `ensure_env_loaded()` places it into `os.environ` in the live process. Because the merge cannot unset an inherited key, choice **(A) overwrite to empty** in `options.env` is genuinely required — without it the subprocess inherits a real API key and could bill it. Avoid **(B)** `os.environ.pop(...)` (mutates global state; races concurrent calls — §10 R-CONCURRENCY). The design chooses **(A)** + a runtime guard (§6) that aborts if `apiKeySource != "none"`.

**"Empty == no key" is a bundled-CLI assumption, not a proof [folded in — review-confirmed]:** whether the bundled CLI treats `ANTHROPIC_API_KEY=""` as "no key" (vs "present but empty → error/odd fallback") is the bundled binary's behavior, not the SDK's. Supporting (not conclusive) evidence: the SDK's own resume-credential code uses truthiness (`opt_env.get("ANTHROPIC_API_KEY") or os.environ.get(...)`), so `""` is falsy *there* — but that is NOT the CLI's `apiKeySource` decision. → §9 step 1 makes this falsifiable: leave a **dummy non-empty** `ANTHROPIC_API_KEY` in `os.environ`, overwrite to `""` via `options.env`, and assert `apiKeySource == "none"` AND the run succeeds on the subscription; repeat with a syntactically-valid-but-bogus key to confirm `""` actually suppresses it. If `""` proves insufficient, the only correct fallback is to build `options.env` from a **filtered minimal allowlist** of needed vars (not `os.environ.pop`).

**`env=` vs `os.environ`:** inject via **`options.env`** (keeps the token off long-lived global state, matches "token lives only in token-store"). The token is env-only — never in argv (there is no CLI flag for the token).

**[DESIGNED-not-proven]:** the probe set the token + `CLAUDE_CONFIG_DIR` on **process env** (`probe.py:25-27`), not via `options.env`; the env-merge order makes the `options.env` path sound but it was not exercised. → §9 step 1.

**Leak surfaces closed:** never in argv (env-only); never in logs/traces (the `_redact_bridge` of §4 wraps args/results/errors, **including the bridge catch-all**); never in `apiKeySource`/`_redacted_status` (token-store contract); the `StoredTokenRecord` is never serialized.

---

## §6 SDK message → AgentEvent MAPPING + error semantics

**Contract re-verified:** `stream_llm` is a plain `def` returning an `AsyncIterator[AgentEvent]` (`protocol.py:79-81`) — the SDK driver keeps the 7A two-method shape (sync `stream_llm` returns `self._stream(request)`; `_stream` is the `async def` generator, `claude_code_oauth_driver.py:121-126`). The `EventType` enum is the complete 7-member set (`events.py:22-28`: `thinking`, `thinking_content`, `text`, `tool_start`, `tool_end`, `error`, `done`); the driver must not invent members. Construction form: `AgentEvent(EventType.X, {...})` (positional type + data; never set `timestamp`).

**Completeness is by-POLICY, not by-enumeration [folded in — review-confirmed]:** the parser returns `UserMessage`, `AssistantMessage`, `SystemMessage` (+ `TaskStarted`/`TaskProgress`/`TaskNotification`/`TaskUpdated`/`MirrorError` **subclasses**, which DO satisfy `isinstance(msg, SystemMessage)`), `ResultMessage`, `StreamEvent`, `RateLimitEvent`, and (only if `include_hook_events=True`, which stays off) `HookEventMessage`. **`RateLimitEvent` (`types.py:1269`, parsed at `message_parser.py:320`) and `StreamEvent` (`types.py:1226`) are standalone dataclasses, NOT `SystemMessage` subclasses**, so the `SystemMessage` branch does not cover them. The driver's rule is: **any message type not explicitly mapped below is IGNORED (non-terminal).** `RateLimitEvent` and `StreamEvent` fall under that rule.

**LLMRequest → ClaudeAgentOptions** (R2/R3): `request.model`→`model`; `request.instructions`→`system_prompt`; the composed user message → the prompt. **The prompt is an `AsyncIterable[dict]`, NOT a string** (required for the §7 gate — see below). `request.tools` is **NOT** forwarded as API tool schemas — the tool surface is the in-process `create_sdk_mcp_server` + `allowed_tools`. `call_llm` raises `NotImplementedError("…stream-only; use stream_llm")`.

### Mapping table (R2, verified against `claude_agent_sdk/types.py`; block line cites normalized)

The driver does `async for msg in query(prompt=..., options=...)`, branching on `isinstance(msg, …)` then block type. It maintains a local `id→name` dict from each `ToolUseBlock` to label the later `ToolResultBlock`.

| SDK object (`types.py`) | → AgentEvent | data payload | Notes / proof |
|---|---|---|---|
| `AssistantMessage` — iterate `.content` | (per block) | — | probe; 7A |
| ┗ `TextBlock` | `EventType.text` | `{"content": text.strip()}` | emit only if non-empty after strip. **PROVEN** |
| ┗ `ToolUseBlock` | `EventType.tool_start` | `{"tool": name, "input": _redact_bridge_dict(input or {}, token)}` | record `id→name`; **input redacted (corrected per §4).** **PROVEN (mapping)** |
| ┗ `ThinkingBlock` | `EventType.thinking_content` | `{"thinking": thinking}` | matches the live agent; drop `signature`. **[DESIGNED-not-proven]** |
| ┗ `ServerToolUseBlock` | `EventType.tool_start` | `{"tool": name, "input": _redact_bridge_dict(input or {}, token)}` | POLICY: §2 should prevent these; if they arrive, treat like `ToolUseBlock`. **[DESIGNED-not-proven]** |
| ┗ `ServerToolResultBlock` | `EventType.tool_end` | `{"tool": <looked-up>, "summary": <redacted/sized>[:200], "chars": …}` | **[DESIGNED-not-proven]** |
| `UserMessage` — iterate `.content` **only if `isinstance(content, list)`** | (per block) | — | the list-guard is MANDATORY (`.content` can be a bare `str`; probe) |
| ┗ `ToolResultBlock` | `EventType.tool_end` | `{"tool": name_from_id, "summary": <sized-then-redacted>[:200], "chars": …, "is_error": bool}` | coerce `content`: `str` as-is else `json.dumps(content)`. `is_error=True` is **NOT** terminal. **PROVEN** |
| `ResultMessage` | **`error` if `is_error` else `done`** — the SOLE terminal | see below | guard both `is_error` AND `subtype=="error"` ("subtype can be 'success' while is_error true" seen live). **PROVEN** |
| `SystemMessage` + `Task*`/`Mirror`/`Hook` subclasses | **IGNORE** (emit nothing) | — | init/hook noise. But read the `init` message's `data.get("apiKeySource")` ONCE for the security assertion (below) |
| `StreamEvent` | **IGNORE** (v1) | — | partial text; keep partials OFF (`include_partial_messages` unset) to avoid double-emission. **[DESIGNED-not-proven]** |
| `RateLimitEvent` | **IGNORE** (non-terminal, informational) | — | standalone dataclass, not a `SystemMessage` subclass; covered by the catch-all-ignore policy. **[folded in]** |

**`done` payload (mirror 7A exactly so `query.py`/thread persistence read identical keys):**
```python
AgentEvent(EventType.done, {
    "answer": result_msg.result or "",
    "tools_used": sorted(set(tool_names.values())),
    "provider": "anthropic",
    "model": request.model,
    "token_usage": {
        "input_tokens":  usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "total_tokens":  in_ + out_,
        "cost_usd": result_msg.total_cost_usd,
    },
})
```
Guard `usage = result_msg.usage or {}` (`ResultMessage.usage` is `dict|None`). **[key names DESIGNED-not-proven — folded in]:** `usage` is `dict|None` with **no type constraint on inner keys**; `input_tokens`/`output_tokens` are carried over from the 7A stream-json result object, not an SDK type, and the probe did NOT assert them. Tolerate missing keys (already via `.get(...,0)`); → §9 step 5 asserts `done.token_usage.total_tokens > 0` (or the keys exist) on the smoke turn.

**Security assertion on the init `SystemMessage` — ADVISORY, not the sole gate [folded in — review-confirmed]:** when the first `SystemMessage(subtype=="init")` arrives, read `data.get("apiKeySource")`. `apiKeySource` does **NOT exist anywhere in the SDK source (grep = 0 hits)** — it is a **CLI-emitted runtime field** that survives only because `parse_message` passes the raw CLI dict through verbatim. So it is bundled-CLI-2.1.183 contract, not type-guaranteed. **Primary** "are we billing an API key" defense = the env-side guarantees of §5 (token present + `ANTHROPIC_API_KEY=""`), which ARE SDK/codebase-verifiable. **Backstop** = `apiKeySource`. Abort condition: `data.get("apiKeySource") not in (None, "none")` → emit a single terminal `EventType.error` ("subscription auth not active — refusing to bill an API key") and tear down. **Do NOT treat a *missing* field as success silently AND do not DoS every run on a rename:** if the field is missing (`None`), fall back to the env-side guarantee and fail **loud** with a message naming SDK/CLI-version drift. Re-run §9 step 1 on any CLI bump. The probe only *asserted* the value; it never *aborted* on it.

### Exactly-one-terminal rule + error semantics (R2 §4)

**Invariant (enforced by convention, not the type system):** the stream yields **exactly one** event of type `done` OR `error`, and it is the **last** event. Pre-flight/setup failures (CLI not installed, no token) MAY `raise` out of the generator on first `async for` step (the only sanctioned exceptions, mirroring 7A `:127-135`). Once the SDK `query()` stream has begun, every failure becomes an in-band terminal `error`. Error event shape is the 7A `_err`: `{"error": message, "provider": "anthropic", "model": request.model}` — the reducer reads `data["error"]`.

| Channel | Manifestation | Handling → single terminal `error` |
|---|---|---|
| **(a) In-band SDK error** | `ResultMessage.is_error==True` / `subtype=="error"`, `api_error_status`, `errors:list[str]` | Map `ResultMessage`→`error`, `data["error"] = result_msg.result or str(result_msg.errors) or "claude agent reported an error"`; terminal. **This is also the realistic CLI-echo vector** — see (c). **[partly DESIGNED]** |
| **(b) `AssistantMessage.error`** (`authentication_failed`/`billing_error`/`rate_limit`/…) | turn-level failure that may precede ResultMessage | Do NOT emit a terminal here; record it, let the trailing `ResultMessage(is_error=True)` carry the terminal (avoids two terminals). EOF-fallback (e) catches the no-ResultMessage case. **[DESIGNED-not-proven]** |
| **(c) SDK exception while streaming** | `async for` raises `ProcessError`/`CLIJSONDecodeError`/`CLIConnectionError`/`MessageParseError`/`ClaudeSDKError` (`_errors.py:6-56`) | `try/except ClaudeSDKError as exc`: if no terminal yet, `yield _err(request, _redact_bridge(str(exc), token)[:500])`; return. **SEE corrected leak narrative below.** **[DESIGNED-not-proven]** |
| **(d) Process death (no exception)** | usually collapses into (c) via `ProcessError` | same as (c); else (e) |
| **(e) EOF without terminal** | loop ends, no ResultMessage seen | synthesize ONE `error`: `_err(request, "claude agent stream ended without a result")` — never a silent `done` (port of 7A `:189-205`) |
| **(f) Timeout** | SDK does not self-enforce `_DEFAULT_TIMEOUT_S=180.0` | wrap consumption in `asyncio.timeout(self._timeout_s)`; on `TimeoutError` cancel the query, `yield _err(request, f"…timed out after {self._timeout_s}s")`, return. **[DESIGNED]** — exact cancel call (`ClaudeSDKClient.interrupt()` vs ceasing iteration) picked at build time |
| **(g) Cancellation / GeneratorExit** | consumer stops iterating | do NOT yield (can't during `GeneratorExit`); `try/finally` whose `finally` ONLY tears down the SDK session/subprocess (port of 7A `finally: _terminate(proc)`). Zero terminal events for a cancelled stream is CORRECT |

**CORRECTED token-leak narrative for exceptions [folded in — three reviews concur, re-verified]:** §6c previously named `ProcessError.stderr` as the CRITICAL token-leak path. **That attribution is wrong for the installed SDK:**
- The transport-raised `ProcessError` hardcodes `stderr="Check stderr output for details"` (`subprocess_cli.py:710-713`) — it never carries real subprocess stderr.
- Real subprocess stderr is piped **only if an `options.stderr` callback is registered** (`subprocess_cli.py:472`); otherwise it inherits the parent. The design registers **no** stderr callback.
- On the live path `query.py:340-346` **replaces** the trailing `ProcessError`'s text with `_last_error_result_text` (the CLI's structured error result), so `str(exc)` is the CLI error result, not raw stderr.

Therefore the **realistic** token-echo vectors are: **(1) the in-process bridge-handler exception path (§4 catch-all; `query.py:716-721` echoing `str(e)`) — the dominant one**, and **(2) the CLI error-result text surfaced via channel (a) / `_err`** if the CLI ever echoes env on failure. `_redact_bridge` remains MANDATORY on **every** error string (channels (a)/(c)/(d), the bridge catch-all, and any `options.stderr` callback if one is ever added for debugging) — the **control is correct; only the rationale/source is corrected.** §9 step 6 is reworked to falsify a real leak (inject a token-bearing string through a tool result + the handler-exception path the driver controls) rather than relying on `ProcessError.stderr`, plus an SDK-drift test asserting `ProcessError.stderr` remains the non-sensitive placeholder.

---

## §7 permission_mode DECISION

**This is the user's explicit gate: `bypassPermissions` is acceptable ONLY if §2 + §3 prove the surface is locked.**

**What `bypassPermissions` does (R3):** disables the permission layer for the session — any tool the model can *see* runs with no prompt. Under bypass the safety boundary is **100% the availability surface** (`tools` / `mcp_servers` / `disallowed_tools`) plus any hook. The probe ran with `bypassPermissions` and all built-ins present — the config we must NOT ship.

**Per-call gate candidates (verified from source):**
- **`can_use_tool` — INSUFFICIENT.** Its docstring (`types.py:1808-1812`) says it is *not* invoked for tool calls already permitted by `allowed_tools` or `permission_mode` (the docstring's skip examples are **`"acceptEdits"` / `"bypassPermissions"`** — it does **NOT** list `dontAsk`). It also **requires streaming mode** and is mutually exclusive with `permission_prompt_tool_name` (`_internal/client.py`). Not the universal gate.
- **`PreToolUse` hook — the ONLY universal gate.** Per the same docstring, *"to observe or gate every tool call regardless of permission rules, use a `PreToolUse` hook."* `PreToolUseHookSpecificOutput` supports `permissionDecision` (`types.py:416`).
- **`permission_mode="dontAsk"` — fail-closed alternative.** Docstring (`types.py:1691`): *"Don't prompt for permissions; deny if not pre-approved."* With `allowed_tools=[only our mcp__ names]`, anything not allow-listed is auto-**denied**. **[DESIGNED-not-proven]** (docstring-only). **[corrected per review]:** the `dontAsk × can_use_tool` interaction is **unspecified in 0.2.105** — do NOT claim `can_use_tool` is skipped under `dontAsk` (only `acceptEdits`/`bypassPermissions` are documented skips). Fold this into the F5 spike.
- **`permission_mode="auto"` — REJECTED for the right reason [corrected per review].** `auto` is **documented** (`query.py:61`: *"A model classifier approves or denies each tool call"*) — the prior "undocumented" rationale was wrong. It is rejected because tool admission must be **deterministic, not model-judged**, not because it is undocumented.

**`permissionDecision` has a `"defer"` value the design must handle [folded in — review-confirmed]:** `permissionDecision: Literal["allow","deny","ask","defer"]` (`types.py:416`); a `"defer"` return creates a `DeferredToolUse` (`types.py:1187`). The `PreToolUse` deny-gate MUST return `"deny"` (never `"defer"`, which would leave the call pending rather than refused) and must treat any non-`"deny"` outcome for an off-list tool as a bug.

**✅ VALIDATED LIVE (2026-06-19): Option 2 (`dontAsk`) PASSED the §9 step-0 spike — `bypassPermissions` (Option 1) was never needed; the hinge below is MOOT (kept for history).**

**RECOMMENDATION — fail-closed, `dontAsk` FIRST [REORDERED per gpt-5.5 review 2026-06-19]: prefer the permission mode that needs NO `bypassPermissions`.**
- **Option 2 (NOW PRIMARY — spike FIRST) — `permission_mode="dontAsk"` + `allowed_tools=[only mcp__ark__*]` + `tools=[]`.** Fail-closed at the permission layer: anything not allow-listed is auto-**denied**, with NO `bypassPermissions` and NO hook. Structurally deny-by-default — the cleanest satisfaction of the user's gate because it avoids `bypassPermissions` entirely. `dontAsk`'s deny behavior is docstring-only (**[DESIGNED-not-proven]**), so it MUST be spiked first: assert a positive `mcp__ark__*` tool call SUCCEEDS and a built-in (`Bash`) is DENIED. Still layered over `tools=[]` + `disallowed_tools` + the §4 Python-side in-process veto.
- **Option 1 (FALLBACK — only if Option 2 fails) — `bypassPermissions` + a `PreToolUse` hook as a hard deny-gate.** The hook denies ANY tool whose name is not in `{mcp__ark__<allowlisted>}` (and explicitly denies all bare-PascalCase built-ins), and can inspect *input* (closing ambiguities #1/#2 — deny `get_portfolio_analysis` if `holdings` present; deny `get_report` if `file_path` resolves outside the sandbox). Keeps the probe-proven `bypassPermissions` auth/run path while adding a fail-closed gate that does not rely on `tools=[]`/allowlist semantics being perfectly enforced. **Backed by the §4 Python-side in-process veto**, which is the only gate that does NOT depend on the CLI. Adopt ONLY if Option 2's `dontAsk` cannot complete a positive tool call or cannot deny built-ins.

**THE OPTION-1 HINGE IS UNVERIFIED — SPIKED ONLY IF OPTION 2 FAILS [folded in — review-confirmed; reordered per gpt-5.5]:** Option 1's enforcement is entirely CLI-side (`query.py` only *relays* the hook's `permissionDecision`; nothing in Python denies), and the probe used **no hook at all**. If the bundled CLI evaluates `bypassPermissions` **before** consulting `PreToolUse` for the allow/deny decision (plausible — "bypass" can mean "skip permission evaluation"), the hook's `deny` could be **ignored** and the whole fail-closed posture collapses to fail-open. This is exactly WHY Option 2 (`dontAsk`, no bypass) is spiked FIRST. **The Option-1 hinge spike (a §9-class gate) runs ONLY if Option 2 proves unusable:** `bypassPermissions` + a `PreToolUse` hook that denies `Bash`, with a prompt that forces a `Bash` attempt, and assert `Bash` never executes AND the hook recorded a deny. Do NOT rely on `bypassPermissions`+hook until this single behavior is empirically confirmed on CLI 2.1.183.

**The user's gate is satisfied because the PRIMARY path (`dontAsk`) needs NO `bypassPermissions` at all** — it is fail-closed at the permission layer over the locked availability surface (§2 `tools=[]` + `disallowed_tools` + §3 allowlist + `strict_mcp_config`) plus the §4 Python-side in-process veto (the one CLI-independent control). **`bypassPermissions` is reached only in the Option-1 FALLBACK, and even there only BECAUSE** that locked surface is layered UNDER the `PreToolUse` deny-by-default hook AND the Python veto — so bypass is never the *only* control. If the Option-1 hinge spike fails, Option 2 already satisfies the gate without bypass.

**Concrete shape change from the probe [DESIGNED-not-proven]:** any per-call gating (`PreToolUse` hook input inspection OR `can_use_tool`) requires the prompt to be an `AsyncIterable[dict]`, not the probe's string (verified-required). The driver's `_compose_input` must yield a one-item async iterable wrapping the composed user message. → §9 step 7.

---

## §8 FACTORY / live-path WIRING

> **✅ STATUS UPDATE (2026-06-20 — §8 EXECUTED).** The "Current state" + "Order of
> operations" below are the as-DESIGNED record; what actually shipped:
> - **Step 1 (SDK driver) DONE** — `src/auth_drivers/claude_code_sdk_driver.py`
>   (`5f0ea35`; + executor and temp-dir/history fixes `b558bde` / `de8e8e9`).
> - **Step 2 (factory repoint) DONE `e52d38f`** — `build_driver(anthropic,
>   claude_code_oauth)` now returns `AnthropicClaudeCodeSdkDriver` (gained optional
>   `registry`/`dal` kwargs). The experimental `--bare` driver is **no longer
>   wired** (kept importable for diagnostics) — so the "**Current state**" line just
>   below (factory constructs `AnthropicClaudeCodeOAuthDriver`) is **SUPERSEDED**.
> - **Step 3 (`live_anthropic_client` stays fail-closed) HOLDS** — the sync
>   `.messages` sites are untouched (OQ-6, out of scope).
> - **Step 4 (Research-stream consumer) DONE (7B-6)** — it **EXISTS now**:
>   `_anthropic_subscription_stream` + the `/query/stream` anthropic branch in
>   `src/api/routes/query.py` route to `driver.stream_llm` when the active anthropic
>   credential is `claude_code_oauth`. Live-smoked (driver-level + route-helper):
>   real `get_sa_feed` on the subscription, built-ins absent, no token leak.
> - **Boundary (explicit):** 7B-6 wires the **streaming** path (`POST /query/stream`)
>   ONLY — the AI 研究 product surface uses streaming. The legacy **non-streaming**
>   `POST /query` for an OAuth-active anthropic credential **still fail-closes**
>   (unchanged); acceptable for now. Wiring non-stream `/query` is a later optional
>   follow-up.

**Current state (re-verified `factory.py:115-130`):** the `(anthropic, claude_code_oauth)` branch constructs the EXPERIMENTAL `AnthropicClaudeCodeOAuthDriver` (the `--bare` driver), with a comment that it is SUPERSEDED (2026-06-19), cannot auth the subscription, and is kept only "so the experimental driver stays constructible for dev diagnostics."

**`live_anthropic_client` is the WRONG integration point [CORRECTED — review BLOCKER, re-verified against the codebase]:** the prior §8/F8 said "un-fail-close `live_anthropic_client` LAST." That is wrong. `live_anthropic_client()` (`live_resolver.py:96-113`) returns a **SYNC `anthropic.Anthropic`** client (`.client_sync()` for db_api_key; bare `Anthropic()` for env-fallback; `raise SubscriptionDriverNotWiredError` for OAuth-active). Its consumers call `client.messages.create(...)` / `client.messages.stream(...)` directly:
- `card_synthesis.py:146,464` (`client.messages.create`),
- `anthropic_agent/agent.py:367,372` (`client.messages.stream`),
- `agents/shared/subagent.py:407`, `compressor/summary_callers.py:97`, `tools/code_generator.py:160`, `agents/cli.py:614`.

The SDK driver is **stream-only** (its `call_llm` raises `NotImplementedError`), **subprocess-based**, and exposes **no `.messages` / `.client_sync()`**. Repointing `live_anthropic_client` to it would **break** card synthesis / the live agent / compression (a stream-only subprocess driver cannot satisfy `.messages.create`), or silently fall through to env-fallback — **billing the env API key, the exact thing the 7A-0 fail-close exists to prevent.** Separately, **`stream_llm` has ZERO consumers anywhere outside `auth_drivers/`** (grep-confirmed) — the Research-stream consumer that would actually drive this driver **does not exist on the live path yet**.

**Order of operations (CORRECTED):**

1. **Build the SDK driver as a NEW class** `AnthropicClaudeCodeSdkDriver` in a new module (`src/auth_drivers/claude_code_sdk_driver.py`), reusing the 7A helpers (`_map` shape, `_err`, `_redact`→`_redact_bridge`, the cap constants). Do NOT overwrite the experimental `claude_code_oauth_driver.py` in this slice — keep it for diagnostics until the SDK driver passes §9.
2. **Repoint `factory.py`** `(anthropic, claude_code_oauth)` branch from `AnthropicClaudeCodeOAuthDriver` to the new SDK driver. Signature/allow-sets unchanged (`_ALLOWED_MODES` already permits `anthropic+claude_code_oauth`); only the import + constructed class change. `token_store` is already threaded (`:127`).
3. **`live_anthropic_client` stays UNCHANGED and fail-closed for OAuth-active.** Card synthesis / the live agent / compression / code-gen MUST NOT route through a subscription subprocess driver. It is a **separate, explicit decision** whether those sync `messages.create`/`messages.stream` sites ever get their own subscription path; that is OUT of 7B-3 scope.
4. **Wire the actual Research-STREAM consumer (PREREQUISITE, not a guard flip).** The driver attaches to a NEW consumer that calls `ResearchProviderDriver.stream_llm` and consumes `AgentEvent`s into the C-2 Research SSE/trace/thread-persistence surface. **This consumer does not exist today** and must be built/named before the live path can use the driver. The flip to live is gated on: (a) the SDK driver exists, (b) §9 smoke confirms subscription auth + one tool call + NO api-key billing + built-ins dead + no token leak + the §7 hinge spike passes, and (c) human + gpt-5.5 sign-off. **[DESIGNED-not-proven]** — the Research-stream consumer's exact shape is a build-time design item.

**What stays gated after wiring:**
- `chatgpt_oauth` (S3) remains the `NotImplementedDriver` placeholder (`factory.py:128`, `_MODE_SLICE` S3) — untouched by 7B.
- The Settings UI surface for selecting `claude_code_oauth` stays behind whatever flag the workbench uses; this design does not enable a UI toggle.
- `discover_models()` / `test()`: `test()` is the §9 smoke; `discover_models()` is auth-mode-specific (the `claude_code_oauth` model set is NOT the api_key set — `protocol.py:96-98`) and can return a curated static list initially. **[DESIGNED]** — out of this slice's critical path.

---

## §9 MINIMAL LIVE SMOKE plan

Falsifiable, minimal-cost. Cheapest acceptable model (per the live-verify-cheap-models convention; `claude-sonnet-4-6` as the probe used, or a cheaper Haiku-class if available on the subscription). Single short turn, one tool call. **All steps run against bundled CLI 2.1.183 under the FULL locked config (the same `options` the live driver ships), and are BLOCKING release gates re-run on any CLI bump.**

**Pre-conditions:** a valid `CLAUDE_CODE_OAUTH_TOKEN` in the token-store; `claude_agent_sdk` 0.2.105 + bundled CLI 2.1.183 (confirmed); the bridge built with the Tier-1 allowlist; `permission_mode="dontAsk"` per §7 Option 2 — the PRIMARY posture, **validated by the live spike 2026-06-19 (PASS)**. The Option-1 `bypassPermissions` hinge is NOT used (it was moot once Option 2 passed).

**Steps (each must pass; any failure blocks the live-path wiring in §8):**

0. **§7 PERMISSION SPIKE (gates everything) — Option 2 `dontAsk` FIRST [reordered per gpt-5.5].** `permission_mode="dontAsk"` + `allowed_tools=[mcp__ark__...]` + `tools=[]`, with NO `bypassPermissions` and NO hook. **Assert (a)** a positive `mcp__ark__*` tool call SUCCEEDS, AND **(b)** a built-in (`Bash`) is DENIED. *(Falsifies "`dontAsk` can serve Research fail-closed without bypass.")* **If Option 2 passes → adopt it and SKIP the Option-1 hinge entirely.** **Only if Option 2 fails** (cannot call the tool, or does not deny built-ins) run the Option-1 hinge: `bypassPermissions` + a `PreToolUse` hook denying `Bash`; assert `Bash` never executes AND the hook's deny was recorded (positive in-process deny counter). *(Falsifies "the hook's deny is honored under bypass.")* **✅ RESULT (2026-06-19, live spike): Option 2 PASSED** — init `tools` = `['mcp__ark__probe_tool']` only (built-ins stripped), stub tool called + sentinel returned, `apiKeySource='none'`, CLI 2.1.183, cost $0.0115; **F1 PROVEN, F10 disproven**. Option-1 hinge NOT run (moot).
1. **Subscription auth, no API-key billing.** Leave a **dummy non-empty** `ANTHROPIC_API_KEY` in `os.environ`; `options.env` injects the token + `ANTHROPIC_API_KEY=""` + empty `CLAUDE_CONFIG_DIR`. **Assert** init `SystemMessage.data["apiKeySource"] == "none"` AND the run succeeds. Repeat with a syntactically-valid-but-bogus key to confirm `""` suppresses it. *(Falsifies "we're secretly billing an API key"; closes §5 `options.env` + empty-key flags.)*
2. **One real tool call UNDER the full locked config.** With `tools=[]` SET (not just bypass), prompt "Give me the SA feed for AAPL". **Assert** the stream contains `tool_start` + `tool_end` for a `mcp__ark__*` tool with non-empty `chars`. *(Falsifies BOTH "the bridge tool isn't reachable" AND "`tools=[]` killed MCP tools too" — the conjunction §2 requires.)*
3. **Built-ins are dead (two assertions).** Prompt strongly inducing `Bash`/`Read` (e.g. "run `ls` / read /etc/passwd"). **Assert (1)** zero `tool_start` with a bare-PascalCase / non-`mcp__ark__` name appears in the stream, AND **(2)** a positive deny record from the `PreToolUse` hook's own in-process counter (or `include_hook_events=True` HookEvent deny frame). *(The two-part assertion prevents a FALSE PASS where the model simply declined to call the built-in and the gate never fired — the AgentEvent vocab has NO `tool_blocked` member, so absence-of-`tool_start` alone is insufficient.)*
4. **Off-allowlist ArkScope tool is refused (gate AND Python veto).** Attempt `mcp__ark__save_report` (a known write tool NOT in the allowlist). **Assert** it is denied / never executes, AND the §4 Python-side in-process veto returned `is_error` for it. *(Falsifies "the allowlist leaks to off-list ArkScope tools"; proves the CLI-independent gate.)* Add a sibling case: `get_report` with `file_path` traversal (`../../config/.env`) → assert refusal (input-level gate).
5. **Exactly-one-terminal + clean trace.** **Assert** the stream ends with exactly one `done` (or `error`), last; `done.token_usage.total_tokens > 0` and `cost_usd` is populated from `ResultMessage.total_cost_usd`. *(Falsifies the §6 terminal-rule + the usage-key DESIGNED-not-proven flag.)*
6. **Token + unknown-secret never leak (reworked — does NOT rely on `ProcessError.stderr`).**
   - **6a (the dominant vector):** register a tool that **raises** `RuntimeError("key=" + token)` and a tool that **returns** the literal token in its result. **Assert** the token substring appears in **none** of: `done.answer`, `tool_end.summary`, the `tool_start.input` echo, scratchpad rows, chat history, or any `error.data["error"]` — and that the surfaced text shows `[REDACTED]`. Also assert no 8+-char contiguous substring of the token appears anywhere. *(Falsifies the §4 catch-all + §6c handler-exception leak.)*
   - **6b (model-facing residual, per the OQ-5 decision):** inject an `sk-ant…`-shaped string into a tool result and assert it is handled per the chosen path (regex-redacted on the full body if (a); or documented-curated-absent if (b)).
   - **6c (SDK-drift guard):** assert the transport-raised `ProcessError.stderr` remains the non-sensitive placeholder `"Check stderr output for details"`.
7. **Streaming-prompt + hook works** (Option 1). **Assert** the `AsyncIterable[dict]` prompt form drives a successful turn with the `PreToolUse` hook attached (closes the §7 shape-change flag).
8. **Isolation backstop.** **Assert** the init `SystemMessage` / `mcp_status` shows ONLY the `ark` server and zero unexpected tools (empirical catch for a managed-settings or MCP re-introduction — §1).

**Cost control:** one short turn per step, cheapest model, `max_turns=3` (probe used 3; 7A default 8 — use 3 for the smoke). Steps 3/4/6 can share a single transcript where the prompt induces the off-surface attempts.

---

## §10 OPEN QUESTIONS / DESIGNED-not-proven flags / risks

**Consolidated [DESIGNED-not-proven] flags — all are bundled-CLI-2.1.183 behavior claims (closed by §9 or a pre-build spike):**
- **F1 — `tools=[]` removes built-ins at runtime** (§2). Docstring + flag-verified; NOT exercised. → §9 step 3.
- **F2 — token injection via `options.env`** (§5). Env-merge order makes it sound; probe used process env. → §9 step 1.
- **F3 — `CLAUDE_CONFIG_DIR` via `options.env`** (§1). Same as F2.
- **F4 — exception-path token leak [RE-SCOPED, was "ProcessError.stderr"]** (§4/§6c). The real vector is the in-process bridge-handler exception (`query.py:716-721` echoes `str(e)`; `__init__.py:462` invokes the handler with no redaction); `ProcessError.stderr` is a hardcoded placeholder (`subprocess_cli.py:710-713`) and `query.py:340-346` replaces ProcessError text with the CLI result. → §9 step 6.
- **F5 — `dontAsk` deny behavior + its `can_use_tool` interaction** (§7). Docstring-only; interaction unspecified in 0.2.105. → spike if Option 2 is chosen.
- **F6 — `bypassPermissions` + `PreToolUse` deny is honored (THE HINGE)** (§7). CLI-side enforcement, no hook in the probe; if bypass short-circuits the hook, Option 1 fails open. → §9 step 0 (gates all).
- **F7 — streaming-prompt + `PreToolUse` hook** (§7). Required for per-call gating; probe used a string prompt + bypass with no hook. → §9 step 7.
- **F8 — `ThinkingBlock`/`ServerTool*Block`/`StreamEvent`/`RateLimitEvent`/`AssistantMessage.error` mappings + the `usage` inner-key names** (§6). Mapped by analogy to the live agent; not exercised. → §9 step 5 (usage keys).
- **F9 — `apiKeySource` is a CLI-runtime field (0 SDK source hits)** (§6). Advisory backstop, not the sole gate; env-side guarantee is primary. → §9 step 1.
- **F10 — `tools=[]` does NOT also suppress MCP tools** (§2). Conjunction unproven (probe proved MCP reachable *without* `tools=[]`). → §9 step 2.
- **F11 — `maxResultSizeChars` extra-field on `ToolAnnotations`** (§4). Honored via pydantic-permissive + `getattr`; a `extra="forbid"` bump breaks construction. → SDK-upgrade check; `truncate_with_marker` is the real guarantee.
- **F12 — Research-stream consumer shape** (§8). The `stream_llm` consumer does not exist on the live path yet; build-time design item.

**Human decisions required (cannot be defaulted):**
- **OQ-1 — the five §3 ambiguities** (`get_portfolio_analysis` args; `get_report` path traversal; IBKR option-chain tools; cache-writing reads; personal-config reads). **DECIDED (gpt-5.5 2026-06-19): v1 = Tier-1 (11 tools) ONLY; ALL FIVE ambiguous tools stay EXCLUDED from v1.** Promote individually later, and only with a wrapper or `PreToolUse` *input* check (§7) for the arg-carrying ones (`get_portfolio_analysis`/`get_report`).
- **OQ-2 — `synthesize_signal`/`get_signal_factors` exclusion** is a *policy* choice (`project_signal_subsystem`), not a safety one. **DECIDED: EXCLUDE in v1** (derived/policy signal, not objective evidence; revisit once the Research evidence surface is stable).
- **OQ-3 — web egress posture.** Mutually exclusive: (a) no web in v1; (b) allow-list `tavily_*` as the controlled egress path; (c) re-enable Claude Code's built-in WebSearch/WebFetch under its own gate. The constraint disables built-in web tools, so (b)/(c) need an explicit decision. **DECIDED (gpt-5.5 2026-06-19): (a) NO web in v1** — local/controlled read-only tools only; web/search is a separate later design.
- **OQ-4 — permission posture** (§7). **DECIDED (gpt-5.5 2026-06-19): Option 2 (`dontAsk`) is PRIMARY — spiked FIRST; Option 1 (`bypassPermissions` + `PreToolUse` hinge) is the FALLBACK, used only if `dontAsk` can't complete a positive tool call or deny built-ins.** Prefer the mode that needs no bypass. §7 + §9 step 0 updated accordingly.
- **OQ-5 — model-facing redaction residual** (§4). **DECIDED: (a) STRICT — `probe_harness.redact` (regex) + exact-token scrub on the FULL model-facing tool-result body, not just the 200-char preview.** Minor over-redaction (CUSIP/base64) accepted — auth/tool bridge, safety first. → §9 step 6b asserts the strict path.
- **OQ-6 — the sync `messages.create`/`stream` OAuth path** (§8). **DECIDED: explicitly OUT-of-scope for 7B-3.** 7B solves only AI 研究 Claude-subscription Research; card synthesis / live agent / compression / code-gen stay api-key-only under the unchanged `live_anthropic_client` fail-close. Whether they ever get a subscription path is a separate future slice.

**Risks:**
- **R-CONCURRENCY (significant) [DESIGNED-not-proven]:** the token, `ANTHROPIC_API_KEY=""`, and `CLAUDE_CONFIG_DIR` are injected via `options.env` (per-call, NOT process-global) — good, avoiding the classic `os.environ` race. **Guard:** confirm Option A (no `os.environ.pop`) is sufficient so NO `os.environ` mutation occurs, and that each concurrent `stream_llm` gets its **own** temp dirs (no shared mutable `CLAUDE_CONFIG_DIR`, no module-level client). The 7A model spawns one process per call; preserve that per-call isolation.
- **R-COST:** subscription billing is per the Anthropic plan, not metered per token here, but `done.token_usage.cost_usd` (from `ResultMessage.total_cost_usd`) gives a per-turn signal; surface it but treat the subscription quota as UNKNOWN (`get_quota_status` returns honest UNKNOWN per `protocol.py:83-85`). No fake "X% left."
- **R-CLI-VERSION-DRIFT (was R-SDK-VERSION-DRIFT — re-scoped):** the load-bearing component is the **bundled CLI** (flag enforcement, env-merge consumption, `apiKeySource`, empty-key handling, bypass-vs-hook ordering), version **2.1.183**, which versions **independently of the pip SDK 0.2.105**. The driver MUST pin/assert the CLI version at init (`claude_agent_sdk._cli_version.__cli_version__` or `claude -v`) and fail-closed if it differs from the version §9 validated against. §2's belt-and-braces (`tools=[]` + `disallowed_tools` + `PreToolUse` gate + the §4 Python veto) is deliberately redundant to survive one shift; §9's negative tests (esp. steps 0/3/4/6) MUST be re-run on any CLI bump.
- **R-OVER-REDACTION (minor):** `probe_harness.redact`'s base64≥16 / long-digit rules can over-redact legitimate output (a CUSIP blob, a base64 chart). Acceptable for the 200-char preview + error text. Whether it also applies to the full model-facing body is OQ-5.

---

**Files verified for this synthesis (read or grep-confirmed in this task):**
- ArkScope: `src/auth_drivers/protocol.py:1-104` (sync-`def`-returning-async-iterator `stream_llm` at `:79-81`); `src/auth_drivers/factory.py:1-131` (SUPERSEDED `--bare` branch `:115-130`, `_ALLOWED_MODES` `:35-38`, `token_store` thread `:127`); `src/auth_drivers/claude_code_oauth_driver.py:1-298` (7A `_map`/`_err`/`_redact`/cap constants); `src/auth_drivers/live_resolver.py:1-128` (**`live_anthropic_client` is SYNC `.client_sync()` `:96-113`; OAuth-active fail-close `:110-112`**); `src/agents/shared/events.py` (7-member `EventType` `:22-28`); consumers of `live_anthropic_client` (`card_synthesis.py:146,464`; `anthropic_agent/agent.py:367,372`; `subagent.py:407`; `compressor/summary_callers.py:97`; `code_generator.py:160`; `cli.py:614`) — **`stream_llm` has 0 consumers outside `auth_drivers/`**; `src/tools/report_tools.py:256-265` (**`get_report` path traversal — no containment check**); `src/auth_drivers/probe_harness.py:26,57` (`redact`); `src/agents/shared/compressor/reducers.py:48,427` + `summary_prompt.py:148` (`truncate_with_marker`, `get_reducer`, `LAYER_5_CHAR_CAP=12_000`); `src/auth_drivers/token_store.py:33-52` (`metadata` excluded from `_redacted_status`); `/tmp/agent_sdk_probe.py:25-27,64-75` (the fail-OPEN config the probe exercised).
- SDK `claude_agent_sdk` 0.2.105 (`/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/claude_agent_sdk/`): `_cli_version.py` (**`__cli_version__="2.1.183"`**); `__init__.py:462` (handler invoked with no redaction); `_internal/query.py:716-721` (`str(e)` echoed to CLI), `:641-643` (`tools/call` dispatch), `:340-346` (ProcessError text replaced by CLI result); `_internal/transport/subprocess_cli.py:83-91` (bundled CLI preferred), `:245/:266/:341/:353` (`--tools ""`/`--disallowedTools`/`--strict-mcp-config`/`--setting-sources=`), `:430-435` (env MERGE, no delete), `:472` (stderr piped only with callback), `:710-713` (**`ProcessError(stderr="Check stderr output for details")` hardcoded**); `_internal/message_parser.py:320` (`RateLimitEvent`); `types.py:32` (`SettingSource` = user/project/local), `:416` (`permissionDecision` incl. `"defer"`), `:1080/1169/1226/1269/1283` (Task/Mirror subclasses vs standalone `StreamEvent`/`RateLimitEvent`), `:1641-1652` (`tools`/`allowed_tools` orthogonality), `:1691` (`dontAsk`), `:1808-1812` (`can_use_tool` skip examples = acceptEdits/bypassPermissions only); `query.py:61` (`auto` documented); `apiKeySource` grep across SDK = **0 hits**.

---

## 7B-3 review incorporation

**Lens 1 — TOOL-SURFACE ESCAPE (`surface_locked` verdict: Conditional, "designed-locked, not proven-locked").** VERDICT ACCEPTED.
- ACCEPT (high) Locks are enforced by the opaque bundled CLI, not the Python SDK — re-scoped all flags to bundled-CLI-2.1.183, added version pin/assert + R-CLI-VERSION-DRIFT (§0 header, §1, §10).
- ACCEPT (high) The only proven config is the OPEN one — stated explicitly in §0; §9 steps 0/1/3/4/6/7 are blocking pre-merge gates.
- ACCEPT (medium) Managed/enterprise settings outside `setting_sources=[]` — added §1 assumption + §9 step 8 empirical backstop (verified `SettingSource` is user/project/local only).
- ACCEPT-with-correction (medium) §6c overstates `ProcessError.stderr` — corrected; verified hardcoded placeholder + callback-only piping (kept redaction).
- ACCEPT (medium) §9 deny-signal not in AgentEvent vocab — §9 step 3 now asserts absence-of-`tool_start` AND a positive hook deny-counter (verified the 7-member enum has no `tool_blocked`).
- ACCEPT (medium) PreToolUse-under-bypass is the hinge — promoted to §9 step 0 gating spike + `defer`-handling note (verified `permissionDecision` `"defer"` at `types.py:416`).
- ACCEPT (medium) `get_report` traversal vs name-allowlist — verified `report_tools.py:256-265`; kept excluded + input-level gating rule.
- ACCEPT (medium) Read-only ≠ leak-safe; redaction is load-bearing — elevated to a hard gate (§4, §9 step 6).
- ACCEPT (low) `ANTHROPIC_API_KEY=""` empty-as-no-key is a CLI assumption — §9 step 1 made mandatory with a dummy real key.
- ACCEPT (low) `can_use_tool` is no independent backstop under bypass — added the §4 Python-side in-process veto (verified `query.py:634-643` routes without a Python allowlist).
- ACCEPT (low) `tools=[]` + MCP-reachable conjunction untested — §9 step 2 runs under the full locked config.
- ACCEPT (nit) Keep redaction despite wrong source — done.

**Lens 2 — TOKEN/SECRET LEAKAGE + ISOLATION (`surface_locked` verdict: Conditional on 4 leak/isolation gaps).** VERDICT ACCEPTED.
- ACCEPT (high) Uncaught bridge-handler exceptions bypass redaction (`query.py:716-721`, `__init__.py:462`) — made a HARD `try/except BaseException` invariant + §9 step 6a (verified).
- ACCEPT (high) Full model-facing result only exact-token-scrubbed — recorded as OQ-5 with two explicit options + §9 step 6b (verified the §4 split + probe behavior).
- ACCEPT (high) §8 `live_anthropic_client` is SYNC card-synthesis, not the Research stream — §8 fully rewritten; verified `live_resolver.py:96-113` + 0 `stream_llm` consumers.
- ACCEPT (medium) `apiKeySource` not in SDK source — demoted to advisory backstop; env-side guarantee primary; missing-field fails loud not silent (verified 0 grep hits).
- ACCEPT (medium) `ANTHROPIC_API_KEY` in `os.environ` + merge-can't-delete — overwrite-to-empty stated load-bearing; §9 step 1 dummy-key test (verified `:430-435`).
- ACCEPT-with-correction (medium) §6c `ProcessError.stderr` overstated — corrected narrative; redaction kept.
- ACCEPT (medium) Pin the binary + forbid resume/add_dirs/settings/session_store — added §1 "NEVER set" list + bundled-CLI pin (verified bundled preference).
- ACCEPT (low) `'auto'` is documented — corrected §7 rationale (verified `query.py:61`).
- ACCEPT (low) `StoredTokenRecord.metadata` leak surface — added §5 read-only-`access_token` invariant (verified `token_store.py:33-52`).
- ACCEPT (low) Tool-args redaction inconsistency between §4 and §6 — reconciled; §6 row now uses `_redact_bridge_dict`.
- ACCEPT (nit) Literal-substring grep blind spots — §9 step 6 adds an 8+-char contiguous-substring assertion + size-before-redact confirmation.

**Lens 3 — CORRECTNESS + GROUNDING (`surface_locked` verdict: Conditional, plausible-by-construction not proven).** VERDICT ACCEPTED.
- ACCEPT (blocker) §8 targets the wrong integration point; the `stream_llm` consumer does not exist — §8 rewritten, F12 added (verified, same evidence as Lens-2 high #3).
- ACCEPT-with-correction (high) §6c `ProcessError.stderr` path doesn't exist as stated — corrected; F4 re-scoped to the handler-exception vector (verified `subprocess_cli.py:710-713`, `query.py:340-346`).
- ACCEPT (medium) `RateLimitEvent` missing from §6 + not a `SystemMessage` subclass — added an ignore row + by-policy catch-all (verified `types.py:1269`, `message_parser.py:320`).
- ACCEPT (medium) §7 misquotes `can_use_tool` re `dontAsk` — corrected to acceptEdits/bypass-only; `dontAsk` interaction marked unspecified (verified `types.py:1808-1812`).
- ACCEPT (medium) `maxResultSizeChars` is an undeclared extra field — flagged brittleness (F11); `truncate_with_marker` is the guarantee (verified declared `ToolAnnotations` fields).
- ACCEPT (low) `done.token_usage` inner-key names not type-guaranteed — tagged DESIGNED-not-proven + §9 step 5 assertion (verified `usage: dict|None`).
- ACCEPT (low) F8 overstated uncertainty — replaced; `live_anthropic_client` is locatable, the real gap is the absent stream consumer.
- ACCEPT (low) Citation normalization — compressor paths set to `src/agents/shared/compressor/…`; `get_reducer` at `:427`; block-line off-by-ones not propagated (used named symbols).
- ACCEPT (low) §9 under-specified vs corrected leak model — step 6 reworked to inject token via a tool result/handler-exception, plus an SDK-drift `ProcessError.stderr` check.
- ACCEPT-with-lowering (low) F9 `delegate_to_subagent` — kept explicit-omit note but lowered; the material vector is the built-in `Task` (disabled §2) + `agents=None`, and the `mcp__ark__`-only allowlist structurally excludes bridge-only tools.

**Rejected findings:** none outright. Three were ACCEPTED-with-correction rather than as stated (the `ProcessError.stderr` framing in all three lenses — the redaction *control* is correct and retained, but the *source/rationale* was wrong and is corrected; the realistic vector is the in-process handler-exception echo at `query.py:716-721`). No appendix-of-rejections is required because no finding was found factually wrong on its merits.

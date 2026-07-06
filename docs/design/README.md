# Design Docs — Index & Status Map

The problem this fixes: filenames like `P1_2_SPEC.md` don't tell you whether a doc
is **current authority, a shipped-feature reference, a decision record, deferred
v2 design, or a process journal**. This index maps every `docs/design/*.md` to a
**readable title + status + one-line**, so you don't guess from the filename.

**Maintenance rule:** when you add/retire/repurpose a design doc, update its row
here in the same commit. (`docs/design/archive/` is a provenance stub — its
contents were removed 2026-06-07, recoverable via git.)

### Status legend
| Status | Meaning |
|---|---|
| **CANON** | Current authority. Read first. Wins conflicts (hierarchy below). |
| **ACTIVE** | Current plan/build in flight. |
| **SHIPPED** | Feature delivered; spec kept as reference (may need a status-line refresh). |
| **REFERENCE** | Durable knowledge worth keeping (data quirks, patterns, education). |
| **DECISION** | Decision record — *why* we chose X. Durable. |
| **DEFERRED** | v2 / forward design; explicitly not v1 scope. |
| **PAUSED** | Preserved behind a resume gate; not active. |
| **MERGE** | Process journal — fold the load-bearing bits into canon/history; not a standalone authority. |

### Authority hierarchy (on conflict)
1. **`LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md`** — architecture / storage / sync / migration.
2. **`ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md`** — product identity / AI-output contract / permissions.
3. **`CONFIG_AUTHORITY_PLAN.md`** — config source-of-truth rules, file/env retirement gates.
4. **`ARKSCOPE_PROVIDER_CATALOG.md`** — per-provider facts. · **`ARKSCOPE_TOOL_CATALOG.md`** — tool facts.
5. Everything else defers to the above.

---

## CANON — current authority (read first)
| File | Read as | One-line |
|---|---|---|
| `ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md` | **Workbench Product Spec** | Product constitution: identity, AI-output contract, agent boundaries, permission model. |
| `LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md` | **Local-First Architecture Spec** | v1 architecture + storage + sync + page-IA + migration contract (9 locks). Wins architecture conflicts. |
| `ARKSCOPE_PROVIDER_CATALOG.md` | **Provider Catalog** | Per-provider data/latency/streaming/cost/auth/limits → drives Settings provider config. |
| `ARKSCOPE_TOOL_CATALOG.md` | **Tool Catalog** | Live ToolRegistry inventory (~51 tools) with keep/adapt/retire verdicts. |
| `CONFIG_AUTHORITY_PLAN.md` | **Config Authority Plan** | DB-first Settings authority, file/env fallback roles, and retirement gates for config migration. |
| `CURRENT_PROJECT_CONTEXT.md` | **Project Context** | Pointer index for an assistant arriving at the repo; canonical sources in read order. |
| `PROJECT_PRIORITY_MAP.md` | **Priority Map** | Backlog total order + newest-first decision log. First stop for "what's next?". |
| `REFACTOR_PROTECTION_SMOKE_GATES.md` | **Refactor-Protection Gates** | Guardrail protecting operational ingestion + extension runtime paths during refactors/migration. |

## ACTIVE — current build / plan
| File | Read as | Status | One-line |
|---|---|---|---|
| `DESKTOP_APP_VISION_DRAFT.md` | **Desktop App Vision** | ACTIVE | UI/UX + product-surface intent above the SPEC. |
| `DESKTOP_APP_CARRYOVER_ANALYSIS.md` | **Desktop Carryover Matrix** | ACTIVE | 87-component preserve/adapt/concept/defer/drop matrix for the migration. |
| `DESKTOP_SHELL_SPIKE_PLAN.md` | **Desktop Shell Spike Plan** | ACTIVE | Electron+React shell over the FastAPI sidecar (repo layout, lifecycle). |
| `DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md` | **Data Collection & Local Storage Plan** | ACTIVE (DRAFT) | 3 collection modes · 3-way SQLite split · explicit PG runtime-retirement track · price tiers · scheduler/data-update repositioning. |
| `LOCAL_STORAGE_TOPOLOGY.md` | **Local Storage Topology** | DECISION | Source DB vs canonical DB principle; provider-growth review rule for deciding when a new source needs its own DB/inbox. |
| `LLM_AUTH_DRIVER_PLAN.md` | **LLM Auth Driver Plan** | ACTIVE | API-key vs OAuth/setup-token driver realities, token-store rules, Slice 7 Claude subscription driver, and why Claude setup-token needs a tool bridge. |
| `AI_RESEARCH_CONTEXT_MEMORY_PLAN.md` | **AI Research Context & Memory Plan** | ACTIVE | C-2c thread-context principles: complete transcript, no silent truncation, configurable memory policies, strategy/skill/tool extensibility roadmap. |
| `AI_RESEARCH_RUN_LIFECYCLE_PLAN.md` | **AI Research Run Lifecycle Plan** | ACTIVE | Next AI Research architecture: server-owned runs, per-run model selection, attach/replay trace, independent thread execution, and Slice 6/7 ordering. |
| `AGENT_DATA_GAP_FALLBACK_PLAN.md` | **Agent Data-Gap Fallback Plan** | ACTIVE | Structured absence + deterministic fallback plan for SEC/CIK misses, web-search fallback, and provider data-gap diagnostics. |
| `INVESTMENT_SKILLS_PROFILE_DESIGN.md` | **Investment Skills + Investor Profile Design** | ACTIVE | Opt-in investor profile, assistant stance, skill suggestions, and the committed v2 auto-trigger track. |

## Seeking-Alpha pipeline (PROTECTED ingestion path — must not break)
| File | Read as | Status | One-line |
|---|---|---|---|
| `SA_ALPHA_PICKS_CONTENT_CAPTURE.md` | **SA Article Capture** | REFERENCE | How the extension scrapes SA articles → markdown via the native host. |
| `SA_COMMENT_INTELLIGENCE_PLAN.md` | **SA Comment Intelligence** | SHIPPED (stage 1) | Turning SA comments into community signal. |
| `SA_CUTOVER_3D_RUNBOOK.md` | **SA Cutover 3d Runbook** | SHIPPED | PG → `data/sa_capture.db` hard cutover (executed 2026-06-13) + follow-up #1 (comment-signal port, `get_sa_comment_focus`, v1.2 stopwords). |
| `SA_EVIDENCE_FEED_C1_SPEC.md` | **SA Evidence Feed (C-1)** | SHIPPED | `GET /sa/feed` + `get_sa_feed` tool + News-surface SA filter. |
| `SA_EXTENSION_ROADMAP.md` | **SA Extension Roadmap** | ACTIVE | Incremental roadmap for SA extension data coverage. |

## SHIPPED — feature delivered, spec kept as reference
> These `P*`/feature names are the ones you couldn't read from the filename. They are **landed features**, kept as the reference for what was built. Refresh any "no code yet" header lines when touched.

| File | Read as | One-line |
|---|---|---|
| `P0_1_FULL_V1_SPEC.md` | **Replay Harness Spec** | Dual-provider replay safety net (`tests/test_replay_fixtures.py`) that protects refactors. |
| `P1_2_SPEC.md` | **Macro / Calendar Spec** | FRED+Finnhub macro/calendar data layer + as-of/lookahead semantics (delivered). |
| `P1_2_PROVIDER_DISCOVERY.md` | **Macro / Calendar Provider Discovery** | FRED/Finnhub free-tier behavior facts (feed → Provider Catalog, then archive). |
| `P1_3_SPEC.md` | **Seeking Alpha Digest Workflow** | Deterministic SA evidence-pack tool — *reads the existing extension/DB, not a new crawler*. |
| `P1_4_SPEC.md` | **Context Compression Spec** | In-prompt compression + on-disk retention; agent long-context foundation. |
| `MULTI_FACTOR_SIGNAL_DETECTION.md` | **Multi-Factor Signal Detection** | `src/signals/` multi-factor signals (shipped P1; kept-but-adapt; AI-card evidence stays pure-objective). |

## DECISION records
| File | Read as | One-line |
|---|---|---|
| `P1_5_S3_OSS_SPIKE_DECISION.md` | **System Health Dashboard Decision** | Why not sqladmin/Superset; repositioned to a small ops/health view *inside* the workbench. |
| `RL_COLLAPSE_FINDINGS.md` | **RL Collapse Findings** | Why RL is paused/retired (OOS value unproven); current RL-status authority. RL code lives offline under `training/`. |

## DEFERRED (v2) / PAUSED
| File | Read as | Status | One-line |
|---|---|---|---|
| `PHASE_A_KNOWLEDGE_GRAPH_SKETCH.md` | **v2: Knowledge-Graph Memory** | DEFERRED | Forward design; not v1 scope (SPEC §11). |
| `PHASE_D_ANALYSIS_PIPELINE_SKETCH.md` | **v2: Analysis Pipeline** | DEFERRED | Forward design over the `src/analysis/` scaffold; not v1 scope. |
| `PHASE_C_UNIFIED_RUNNER_SPEC.md` | **Unified Runner** | PAUSED | Dual-SDK de-duplication; preserved behind a resume gate. |

## Agent-layer reference (keep; refresh pre-pivot framing)
| File | Read as | Status | One-line |
|---|---|---|---|
| `AGENT_EVOLUTION_TRACKER.md` | **Agent Evolution Tracker** | REFERENCE | Historical record of agent-system phases/decisions (predates canon — point at canon). |
| `AI_AGENT_ARCHITECTURE_PATTERNS.md` | **Agent Architecture Patterns** | REFERENCE | Dexter-derived reusable patterns (scratchpad, token budget, subagents). |
| `SKILL_PLUGINS_RESEARCH.md` | **Skills & Plugins Research** | REFERENCE | Research on Anthropic financial plugins vs our Skills system. |

## MERGE candidates (process journals — fold into canon/history, don't treat as authority)
| File | Read as | One-line |
|---|---|---|
| `LOCAL_FIRST_RESEARCH_WORKBENCH_AUDIT.md` | **Pre-Spec Pivot Audit** | Factual base that fed the SPEC; SPEC now supersedes. |

*(2026-07 docs sweep: the two 2026-05/06 docs-cleanup journals were folded into
`docs/PROJECT_HISTORY.md` §"Docs governance lineage" and deleted — git history is the
archive. Current sweep records: `REPO_HYGIENE_AUDIT_2026_07.md` + `DOCS_SWEEP_DISPOSITION_2026_07.md`.)*

---

*Doc-management note (2026-06-07): the audit verdict for the 75-doc tree was 35 keep / 22 update / 7 merge / 11 discard. The 11 discards (already-archived RL/training/study docs + the executed rename runbook) were removed; the rest are kept. The recurring pain was **unreadable names/status, not uselessness** — this index is the fix. "UPDATE"-verdict docs are kept but have pre-pivot framing to refresh when next touched.*

# AI Research Context & Memory Plan

> **Status:** ACTIVE PLAN (2026-06-15). This is the follow-up plan after C-2a
> AI Research streaming and C-2b thread persistence. It records the principles
> for multi-turn context, user strategy memory, information filtering, and
> future tool/skill extensibility. It is not an implementation spec for one
> narrow endpoint yet.

## 1. Why This Exists

C-2b persists research threads, but persistence is not the same thing as
usable agent memory. A follow-up question such as "what about its valuation?"
needs the agent to understand the current thread. Longer research sessions need
context management. User-specific strategy work needs durable preferences and
style. Future tools need a stable way to be added without rewriting the agent
surface.

This is a core, ongoing product area after the baseline workbench functions are
stable. It should not be rushed into a hard-coded "last N messages" fix.

## 2. Principles

1. **The persisted transcript is complete.**
   Stored thread messages are the source of record. The app must not delete or
   truncate history as a cost optimization.

2. **Prompt context selection is not memory deletion.**
   It is acceptable to choose a subset or summary for a single model call, but
   that choice must not mutate the underlying thread history.

3. **No silent truncation.**
   If a provider cannot accept the selected context, the system should fail
   loudly, ask for a policy change, or use an explicitly configured compaction
   mode. It must not silently drop older turns.

4. **No hidden magic number as product policy.**
   A "last N messages" rule can be an implementation option only if the user
   explicitly selects it. The default policy must not force memory loss behind
   the user's back.

5. **Conversation memory is not current market evidence.**
   Prior turns help interpret the user's intent, but prices, news, filings,
   SA comments, consensus, and other time-sensitive facts still need fresh tool
   calls or evidence snapshots.

6. **Compression preserves access to raw source.**
   P1.4 already established the pattern: summary in prompt, raw payload on disk.
   The same rule applies to future thread compaction.

7. **User strategy memory is explicit and inspectable.**
   The app may learn a user's risk tolerance, preferred holding period,
   valuation style, and research workflow, but those preferences should become
   visible/editable artefacts, not hidden model bias.

8. **Long sessions need replacement-by-summary, not just failure.**
   When a thread/session grows beyond practical provider context, the correct
   steady-state path is to replace old raw turns in the prompt with a durable
   compaction summary, while keeping the raw transcript searchable/retrievable
   for exact details.

## 3. Existing Assets

- **C-2b ResearchThreadStore** persists research threads/messages in the local
  profile-state database. This is the transcript substrate.
- **P1.4 Context Compression** provides an in-run compression library with
  raw-payload retention (`src/agents/shared/context_manager.py`,
  `src/agents/shared/compressor/`). It is a foundation, not a complete
  thread-memory policy: today it primarily compacts tool outputs/message
  projections inside a single agent run.
- **Memory tools** (`save_memory`, `recall_memories`, `list_memories`,
  `delete_memory`) provide explicit long-term notes, but they do not currently
  decide which prior thread turns are injected into `/query/stream`.
- **SA evidence tools** (`get_sa_feed`, `get_sa_comment_focus`, digest/comment
  tools) now give the agent richer research evidence. The memory policy should
  help the agent use those tools, not replace them.

## 4. Immediate C-2c Direction

The first implementation should be conservative and transparent:

- Add a provider-neutral server-side history builder for `/query/stream`.
- Fetch prior non-error messages from the persisted thread before the current
  user turn is sent to the provider.
- Default to **full thread context** in the first cut.
- If the provider rejects the request because the context is too large before
  thread compaction is wired, persist an error turn with a clear message instead
  of silently dropping history.
- Do not introduce summarization, vector recall, graph memory, or fixed caps in
  this first cut.

This gives follow-up questions real context without pretending the hard memory
problem is solved. The next memory cut after this should adapt the P1.4
compaction pattern to persisted Research threads.

## 5. Future Context Policies

These should be configurable in Settings or per thread, not hard-coded:

| Policy | Meaning | Status |
|---|---|---|
| `full_thread` | Send all prior non-error turns. | Default first policy. |
| `no_history` | Treat each turn as independent. | Useful for one-off research. |
| `recent_messages` | Send the last N messages. | Only user-configured; never implicit. |
| `summary_plus_recent` | Send a durable thread summary plus recent raw turns. | Primary long-thread policy after C-2c. |
| `evidence_snapshot_plus_thread` | Send thread history plus selected saved evidence packets. | Later, after evidence snapshots are normalized. |

The policy object should record what was sent for each turn so a user can debug
why an answer did or did not remember something.

For `summary_plus_recent`, the summary is a prompt-context replacement for older
raw turns, not a replacement in storage. If a later question needs an exact
detail, the agent/UI should retrieve or search the raw transcript/evidence
rather than rely on summary wording.

## 6. Compression And Memory Roadmap

1. **Transcript memory** — persisted raw thread messages (C-2b shipped).
2. **Context injection policy** — C-2c, full-thread first, no silent truncation.
3. **Thread compaction** — durable summary artefacts that replace old raw turns
   in prompt context while retaining raw transcript search/retrieval. Reuse
   P1.4 concepts where they fit: compaction marker, recent boundary, circuit
   breaker, raw-retention, and explicit retrieval.
4. **Evidence snapshots** — save the evidence packet/tool trace a turn used, so
   later turns can refer to durable evidence rather than stale prose.
5. **Long-term user preference memory** — investment style, risk tolerance,
   preferred evidence types, time horizon, and recurring constraints.
6. **Strategy/skill artefacts** — turn a conversation about investment style
   into an inspectable, editable skill or policy file.
7. **Knowledge graph / richer recall** — deferred. `PHASE_A_KNOWLEDGE_GRAPH_SKETCH.md`
   remains the long-horizon reference, not a v1 requirement.

External projects such as Hermes Agent, GitNexus, and Graphify are research
references for context management, compaction, and structured memory. They are
not adopted architectures until a specific design review says so.

## 7. Related Post-Baseline Work

These are sibling areas, not distractions.

### Low-Value News / Information Filtering

The app needs better filtering for duplicate, low-signal, or stale information.
The first rule is provenance and auditability: filtered items should be
explainable, and important evidence should not disappear without a trace.

Likely dimensions:

- duplicate and near-duplicate detection;
- source reliability and freshness;
- novelty versus repeated wire copy;
- ticker relevance and event type;
- user feedback ("show less like this", watch/ignore);
- cost-aware fetching for expensive providers.

### User Strategy / Skill Generation

The product should eventually help a user define a personal research strategy
through conversation: risk tolerance, preferred holding period, style
(growth/value/event-driven), evidence preferences, position sizing constraints,
and what counts as a strong or weak signal.

The output should be an editable artefact, such as a skill or strategy profile,
not an invisible prompt tweak. The user should be able to inspect, revise,
disable, export, and version it.

### Tool Interface Extensibility

Adding tools should become routine. A future tool contract should include:

- typed input/output schema;
- source/provenance and freshness fields;
- cost/latency/permission metadata;
- whether the tool is deterministic, provider-native, or LLM-derived;
- whether it is safe for background use or only manual invocation;
- test fixtures and replay expectations.

This keeps the agent extensible without turning every new data source into a
bespoke UI/backend integration.

## 8. Out Of Scope For The Next Cut

- Hidden or uninspectable summarization of threads.
- Fixed hard caps on remembered messages.
- Vector DB or graph memory.
- Automatic inference of user strategy without explicit user approval.
- Replacing fresh data reads with remembered prose.
- Refactoring both provider SDKs into a unified runner.

## 9. Acceptance Criteria For This Plan

- C-2c does not ship as "last N messages" by default.
- A user can understand whether a turn used full history, no history, or a
  configured policy.
- If context is too large, the error is visible and persisted.
- Any future compaction stores summaries as derived artefacts and retains the
  raw transcript.
- Long-thread compaction uses summary as prompt-context replacement for old
  turns and keeps exact-detail retrieval available.
- Strategy memories and generated skills are user-visible and editable.

# ArkScope Terminology and Language Policy

> **Status: ADOPTED TERMINOLOGY POLICY; WRITTEN REVIEW APPROVED WITH P2.8
> SLICE 4.1, 2026-07-19; APP-WIDE I18N AUTONYM ADDENDUM WRITTEN REVIEW
> APPROVED, 2026-07-20.**
> This is the single repository authority for product-facing English and
> Traditional Chinese terminology. Other documents link here instead of
> copying canonical term tables.

## 1. Scope

This document owns:

- canonical English and Traditional Chinese product terms;
- which professional terms remain English in Traditional Chinese copy;
- rules for mixed-language labels and sentences;
- visible-label versus search-alias behavior; and
- the process for adding or changing a cross-surface term.

It does not choose the runtime i18n library, locale detection, string-key
format, fallback implementation, or migration sequence. Those belong to the
separate app-wide i18n decision document.

English and Traditional Chinese remain target interfaces. The current product
has not completed that runtime migration; this policy prevents new copy from
drifting while the implementation is designed.

## 2. Language Rules

### 2.1 Locale owns grammar

English UI uses English grammar. Traditional Chinese UI uses natural
Traditional Chinese grammar. Copy must not be assembled as word-for-word
translation fragments that read unnaturally in either locale.

### 2.2 Preserve professional English when translation loses meaning

Keep a term in English when it is a proper name, protocol, model/product name,
widely used AI or finance abbreviation, stable identifier, or a professional
term whose forced Chinese translation is less precise.

Examples include `Provider`, `OAuth`, `Agent`, `NAV`, `P&L`, `EBITDA`, `ETF`,
`FRED`, model names, ticker symbols, and series IDs.

Preserving an English term does not require English grammar around it. For
example, `Provider 登入與憑證` is valid Traditional Chinese mixed copy.

### 2.3 Prefer mature non-lossy Traditional Chinese

Use established Traditional Chinese where it is natural and equally precise.
Examples include `總經資料`, `全部標的`, `自選股`, `持倉`, `風險意願`, and
`風險承受能力`.

### 2.4 Mixed professional language is the default

Traditional Chinese is not an all-Chinese translation target. A professional
English term may remain inside an otherwise Traditional Chinese label or
sentence when §2.2 applies.

### 2.5 Do not duplicate the same label in two languages

A visible label must not repeat one concept as `譯文 · Original`,
`譯文 / Original`, or parenthetical translation by default. For example,
`總體經濟與行事曆 · Macro / Calendar` is not an accepted naming pattern.

Parallel bilingual display is allowed only for a case-specific product need
with its reason recorded in the owning design. It is not a global display mode.

Recorded exception: after the app-wide i18n release gate passes, the Settings
PageHeader language selector may show `繁體中文` and `English` together as
locale autonyms. The options remain self-named regardless of the current
locale so a user can always recognize the return path. This exception applies
only to the selector options and does not authorize duplicate bilingual labels
elsewhere.

### 2.6 Search aliases need not be visible

English and Traditional Chinese aliases may be indexed in registry keywords or
localized search metadata. Searchability does not require both aliases to be
printed in the interface.

## 3. Canonical Terms

| Concept | English interface | Traditional Chinese interface | Rule or note |
| --- | --- | --- | --- |
| Full tracked inventory | Universe | 全部標的 | Never translate Universe as `宇宙`. |
| Curated or filtered subset | Pool | 池 | Use in compounds such as `標的池`; never use for Research threads. |
| Daily research list | Watchlist | 自選股 | A working view over profile state. |
| Broker portfolio surface | Holdings | 持倉 | Distinct from Universe and Watchlist. |
| Primary work surface | Home | 工作台 | Default Shell destination. |
| Event/news surface | News | 新聞·事件 | Canonical Shell destination label. |
| AI research surface | AI Research | AI 研究 | Distinct from the broader Research workflow group. |
| Shell workflow group | Explore | 探索 | Contains Home, Watchlist, Universe, and News. |
| Research workflow group | Research | 研究 | Workflow group label, not a thread pool. |
| Monitoring workflow group | Monitor | 追蹤 | Contains the Holdings surface. |
| System diagnostics surface | System / Health | System / Health | Preserve the established mixed professional label. |
| Structured §2 output | AI card | AI 卡片 | Carries per-claim traceability. |
| Application preferences | Settings | 設定 | Product surface, not System diagnostics. |
| AI/data service owner | Provider | Provider | Preserve English in Traditional Chinese copy. |
| Delegated authorization protocol | OAuth | OAuth | Preserve protocol name. |
| AI acting component | Agent | Agent | Preserve professional AI term unless an owning domain records a narrower term. |
| Net asset value | NAV | NAV | Preserve finance abbreviation. |
| Profit and loss | P&L | P&L | Preserve finance abbreviation. |
| Earnings before interest, taxes, depreciation, and amortization | EBITDA | EBITDA | Preserve finance abbreviation. |
| Exchange-traded fund | ETF | ETF | Preserve finance abbreviation. |
| Federal Reserve Economic Data | FRED | FRED | Proper product/data-source name. |
| Macro data Settings section | Macro Data | 總經資料 | Natural Chinese is precise; do not duplicate `Macro`. |
| Willingness to accept investment risk | Risk appetite | 風險意願 | Do not use `風險胃納`. |
| Financial ability to absorb loss | Risk capacity | 風險承受能力 | Distinct from willingness. |

Universe, Pool, Watchlist, and Holdings describe different product concepts even
when they read from related local profile data. They are not interchangeable
aliases.

## 4. Labels, Sentences, and Identifiers

- Stable technical identifiers remain unchanged and are not localized.
- Provider/model names, ticker symbols, series IDs, API field names, and error
  codes remain source text where shown legitimately.
- User-facing explanations localize the surrounding sentence and must not leak
  raw exceptions or internal module names.
- Acronyms may receive a concise explanation in supporting copy when needed,
  but the control label remains the canonical acronym.
- A term can have invisible search aliases without adding visible bilingual
  clutter.

## 5. Authority and Change Process

1. New cross-surface terms and changes to canonical pairs are made here first.
2. Domain specs may define specialized vocabulary but must link here for shared
   concepts and cannot silently redefine them.
3. Product specs that previously copied term tables retain only a link to this
   authority.
4. Registry labels, search keywords, tests, and Design Kit copy are synchronized
   in the owning implementation slice.
5. A proposed bilingual-label exception records its audience and reason in the
   owning design before implementation.

The app-wide i18n decision at
[`2026-07-20-app-wide-i18n-decision.md`](../superpowers/specs/2026-07-20-app-wide-i18n-decision.md)
may add locale-specific string keys and translation workflow metadata, but it
does not create a competing terminology table.

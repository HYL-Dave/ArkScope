# SEC Filing Type Names And Groups

Base: `5d22c28b`. The user approved code plus localized purpose, common financial
reports first, and grouping the other submissions. This is presentation only:
no schema, acquisition, API, model-tool, runtime or filing-filter changes.

## Contract

- Only locally returned options are displayed. Metadata is not an allowlist and
  must not invent filings that were not observed.
- Five display groups: reports, events/proxy materials, ownership/transactions,
  offerings/listing, and other filings. Empty groups are omitted.
- Codes, spaces, historical forms, amendments, and aliases remain unchanged.
  For example, `SC 13G` and `SCHEDULE 13G` are separately selectable.
- Names for known `/A` bases identify amendments. Unrecognized forms remain
  selectable under Other, with an unclassified label rather than a guessed name.
- The menu exposes both code and purpose to assistive technology. Group headings
  are not selectable. All, debounce, pagination reset and focus controls remain.

## Sources

These are short UI descriptions, not legal interpretations or completeness
claims. The groups are application navigation categories, not an SEC taxonomy.

The [SEC submission-type index, Volume II Chapter 3](https://www.sec.gov/files/edgar/filermanual/edgarfilermmanual-vol2-c3.pdf)
is the primary source for reports, proxy materials, ownership, offerings,
listing, specialized disclosures and amendments. In particular, PX14A6N is
the roll-up-transaction exempt solicitation notice, not a generic intention to
solicit. The [Form 25](https://www.sec.gov/files/form25.pdf) heading identifies
removal of securities from listing and/or registration; its label must not
assert that the entire issuer is delisted or bankrupt.

Historical and correspondence supplements:

- [10-K405 example in the SEC index](https://www.sec.gov/Archives/edgar/data/0000096669/000089056695000159/0000890566-95-000159-index.htm):
  annual report with historical submission code, not a third-party inference
  about insider reporting compliance.
- [CERTNYS example](https://www.sec.gov/Archives/edgar/vprr/1300/13003770.pdf):
  NYSE listing and registration certification.
- [NO ACT example](https://www.sec.gov/Archives/edgar/vprr/0805/08052351.pdf):
  no-action correspondence.
- [UPLOAD example](https://www.sec.gov/Archives/edgar/data/1878848/0000000000-25-001990-index.htm):
  SEC-generated letter, not a user-upload command.

The checked-in prior browser observation supplies 52 actual local option codes
for bilingual regression coverage. Its saved query result remains unchanged.

## Verification

Initial RED: the three new grouped-description cases fail because the old menu
has no groups. The same cases pass after implementation. A separate RED confirms
the sticky-heading guard fails before removing stickiness. This closes the
independent review's keyboard-occlusion concern without changing navigation.

The first full frontend run had 1,850 passes and two failures in the exact i18n
inventories. Both now enumerate the 47 added leaves (40 names, five groups, two
scalar strings). The historical pre-Slice-5 baseline stays 645; the new paths
are explicitly accounted for rather than weakening that older assertion.

Final focused run: **115 passed** in three files. Final complete frontend:
**1,853 passed** in 124 files, no failures or skips. Typecheck passes. Product
and review follow-up have no remaining static finding.

Production build passes. Its first sandboxed attempt could not write Vite 5's
temporary config bundle beside the read-only config. Repeating with a
byte-identical config copy in private scratch resolves that runner restriction;
product configuration and host filesystem permissions are unchanged. The CJS
config-loader deprecation and existing >500 kB bundle warning are nonfatal.
Tests ran serially with network access disabled, a read-only host and private
caches. No full-backend or cross-platform acceptance is implied.

Actual Desktop viewport verification is pending the rebuilt hand-test launch.

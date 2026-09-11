## Task 4: Settings Filing Reader

**Files:** extend `apps/arkscope-web/src/api.ts`, `settings/SecResearchPanel.tsx`,
`settings/secResearch.css`, English/zh-Hant Settings resources; add
`settings/SecDocumentReader.tsx`, adjacent focused tests and API helper tests.

**Interfaces:** a lucide read/open command on each catalog row opens the document
reader for that exact filing. Initial selection performs stored GET only. Explicit
acquisition POST uses a ten-minute client allowance and offers GET reread when
outcome is unknown, never auto-retries POST. View shows document choice, sections,
literal search, bounded page navigation, capture time and source citation link.

- [ ] RED stored-only opening, original selected filing identity, conflict rows
  retained, stale async response ignored after changing filing/closing, exact
  Unicode text, current/pinned distinction and lostPOSTstate. Ensure pagination
  forwards unchanged cursor and filters and does not silently switch captures.
- [ ] Use a side panel or unframed bounded reader beside/below the table, consistent
  with existing Settings. No fetched HTML rendering, unsafe links, nested cards
  or giant data dumps. Use actual available document entries, form-aware sections
  and plaintext passages. Stable control/table dimensions and mobile scrolling.
  Citation metadata remains available without making it the primary reading text.
- [ ] Complete frontend/typecheck/i18n tests and fixture-only Playwright en/zh-Hant
  desktop/mobile through actual HTTP/service/store with generated transport bodies.
  Verify original/pinned reopening, next/back, section/search, unknown-section gap,
  lostPOSTreread and no unexpected requests. Inspect screenshots for overlaps.
  Independent review and commit; no production App/provider call.

## Final Gates

- [ ] All four task reviews and final whole-change review approved; fix full
  findings lists with RED evidence, not successive undocumented partial reviews.
- [ ] Fresh complete backend baseline8823nodes(8811P/12S); reconcile exact added/
  removed/executed nodes and unchanged skip identities. Freeze source identities
  during execution. Full frontend baseline1738; no guessed passing counts.
- [ ] Mechanical census against the sealed query/Settings batch; report raw
  candidates, uncertainties, coverage/dependency/untracked drift honestly.
- [ ] Archive logs, commands, inverses, reviews, source hashes and browser evidence.
  Update current spec/priority map with actual completed and remaining scope.
  Register SEC-RECOVERY-001/002 as open, not silently completed by this feature.
  No merge/push/production activation. Remove only this plan's disposable scratch
  after evidence is safely published and verified.

## Public Technical Sources

- https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
  documents actual accession directories/index.json and filer-agent CIK distinction.
- https://www.sec.gov/search-filings/edgar-application-programming-interfaces
  distinguishes submissions metadata from extracted XBRL/companyfacts.
These are documentation reads, not authorizations for issuer/provider acquisition.

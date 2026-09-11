# Census Interpretation

Actual baseline is sealed `2026-09-11-sec-query-settings/census-post-fix/census.json.gz`,
as named in that archive's README. The first launcher used an absent flattened
filename and exited1 before publication; its log is retained. Corrected run
`census-final-corrected` and final frozen-source `census-final-fixed` both exit2,
`review_required_not_a_deletion_list`, with the same counts below.

Current1133 source files read,4346 candidates,3460 uncertainties. Against baseline
1119/4360/3444:4 new candidate IDs,166 new uncertainty IDs,0 coverage reductions,
0 dependency metadata drift and0 new untracked names. Of166 new uncertainty IDs,
150 have identical old metadata excluding id/line/column; raw records remain intact.
Eighteen old i18n candidate IDs gain statically recognized consumers; no deletion
was performed to reduce these counts.

The four new candidates are not authorized deletions:

| Candidate | Independent consumer evidence |
| --- | --- |
| GET `/sec-research/filings/{filing_id}/document` | `getSecResearchDocument` constructs a query URL; final browser's84HTTP records per viewport include actual stored index/text/search/pin requests, with19 independently hash-verified passages. Scanner does not resolve this composed URL. |
| en/zh-Hant `secDocument.open` | `SecResearchPanel` uses its typed translator prop for each row's IconButton. Both locale browser runs activate this exact visible command; corresponding React owners exercise conflicting variants and focus restoration. |
| `.sec-record-scroll td .ui-icon-button` | Descendant selector styles that actual row command. Browser screenshots show the cells/buttons; existing CSS/class coverage gates pass. Scanner records unresolved compound selectors rather than proving absence. |

New uncertainties are148 frontend,17 SQL and1 Python. The Python item is the
bounded import fixture in `tests/test_sec_research_document_service.py:31`, not a
new product orphan. SQL/frontend uncertainty remains explicit, with the unchanged
CENSUS-SQL-001 and scanner composed-URL/translator maintenance owners. No registry
waiver, candidate suppression, source deletion or scanner expectation relaxation
was used to obtain this result. The old cleanup queues remain open.

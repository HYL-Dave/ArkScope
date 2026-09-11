## Task 3: Stored Read And Explicit Acquisition HTTP

**Files:** modify `src/api/routes/sec_research.py`, add focused
`tests/test_sec_research_document_routes.py`, adjust exact route-count owners
`tests/test_api.py` and `tests/test_security_lifecycle_routes.py`.

**Interfaces:** GET `/sec-research/filings/{filing_id}/document` with exactly the
DocumentQueries operands. POST at the same path accepts strict
`{document_id:"primary"}` (extra fields forbidden). GET returns closed envelope;
POST returns attempt with status/gaps/capture_id and never pretends a timeout
failed before dispatch. Add two actual routes222->224, no other route removed.
Static segments cannot be captured by existing `/{cik}` routes.

- [ ] RED query/cursor validation before absent/corrupt store handling, zero
  GET acquisition/implicit installation, invalid IDs and permission denial before
  mutation, exact profile identity use and small real-service integration.
- [ ] Connect both real service paths. Profile-configured SecSourcePolicy handles
  each actual SEC request; no env credentials/providerfallback. POST may explicitly
  install a fresh schema but not repair old shapes. Use content-free typed errors.
  Validate malformed operands consistently422 even before installation; valid
  missing store/document is an unavailable envelope, not an empty document.
- [ ] Tests preserve existing six SEC endpoints and current task/registry contracts.
  Run actual mounted route inventory, shared permissions and all SEC suites;
  independent review then scoped commit.


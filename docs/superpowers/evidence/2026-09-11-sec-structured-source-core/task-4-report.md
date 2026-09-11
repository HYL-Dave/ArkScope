# Task 4: Company Facts Parser

Status: implemented and focused GREEN; independent review pending.
Files: src/sec_research/facts.py, tests/test_sec_research_facts.py.

Consumes the Task3 common exact JSON, CIK, date, accession and text validators.
Both modules remain pure and unregistered. Source SHA256 is computed once via
common.source_ref; per-fact IDs separately bind that hash and exact RFC6901
pointer. Original/overlapping/amended facts remain separate immutable records.
No storage, live API, latest-value selection, temporal inference or derivation.

## Test Evidence

- Initial behavior selection before any parser file existed:53setup errors.
  Not claimed as valid RED; the subsequent explicit runtime-owner assertion
  failed exactly before facts.py was created (task4-owner-red.xml).
- First integrated behavior run once common helpers existed:54passed0.28s.
- Actual source inverse value=str(float(value)):4failed, precision and integer/
  non-USD owners. Restored the literal exact str(value) implementation.
- Actual source inverse one-row-per-concept:2failed, YTD/quarter and amendment
  preservation owners. Restored tuple of every original observation.
- Restored full fact scope:54passed (task4-restored.xml).
- Every provider response fixture is hand-constructed JSON; no live provider
  acquisition or production store was used. This is parser verification, not
  an observation of real issuer coverage or completed end-to-end SEC research.

## Self Review

No schema/ABI change outside the new module. Monetary values remain text; exact
large integer, negative, zero and exponent representations survive. Source
pointers resolve the original bytes; duplicate values at different pointers have
distinct IDs. Filing-agent accession prefix need not equal issuer CIK. Missing
optional labels remain None, required invalid shapes fail before returning any
snapshot, and numeric fiscal labels are not conflated with standalone quarters.

Next gate: independent spec/quality review of combined common/catalog/facts
interfaces, then full backend and census. No completion or integration claim yet.

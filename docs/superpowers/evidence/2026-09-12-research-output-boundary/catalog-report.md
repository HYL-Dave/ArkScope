# Confirmed Catalog Residual

Owner: coordinator, independent of the Task 3 fix/re-review. No live credentials,
provider, CLI execution or token-store reads in new tests. Existing subscription
tests execute their disposable fixture CLI through the offline runner.

Source scanning found `_model_identifier` using the same diagnostic scrubber as
a format check. RED reproduced rejected ordinary IDs and credential-bearing
pages reaching parsing/cursor reuse. Not every long ID was rejected: the old
rule depended on exact shape. This report makes no production exposure claim.

The supplied authentication record already contains access, refresh and ID
tokens. A local shared OutputGuard registers these inside the authenticated
callback, preserving prior authentication admission order. Complete model-list
pages are checked before parsing, filtering or cursor reuse. The returned plan
diagnostic is checked too. No ambient execution scope is borrowed and account
usage reads remain unchanged.

The old 80-character lexical contract remains. Explicit three-part JWT syntax
with a decoded algorithm header is rejected as a model identifier; this is not
a general high-entropy or encoded-cursor ban. The existing subscription JWT
test is unchanged and remains an effective negative control.

| Run | Passed | Failed | Error/Skip | Meaning |
| --- | ---: | ---: | ---: | --- |
| catalog-red-01 | 20 | 39 | 0/0 | Behavioral RED in new 59-node suite |
| catalog-green-02 | 171 | 0 | 0/0 | New suite plus subscription and primitive controls |
| catalog-inverse-page-03 | 1 | 36 | 0/0 | Omit page check; all credential placements turn RED, public pagination stays green |
| catalog-inverse-jwt-04 | 19 | 2 | 0/0 | Omit JWT check; new and unchanged old owners turn RED, public IDs stay green |
| catalog-restored-05 | 171 | 0 | 0/0 | Both mutations restored |

Counts overlap and must not be added into a complete-backend total. Commands,
logs and JUnit are in same-named create-only run directories. Whole-branch
review and complete-backend verification remain required.

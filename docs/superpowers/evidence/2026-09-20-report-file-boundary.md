# Report File Confinement

Owner: research report tools. Status: focused verification green; full regression
and activation are recorded in the retirement verification packet.

The audit's arbitrary-file-read defect is confirmed using synthetic canaries
only. No real credential file is read or copied. Before the fix, relative
traversal, absolute paths (including metadata-resolved paths), symlinks and hard
links all returned the synthetic private content. A FIFO also blocked a read.

The report tools now accept only canonical `data/reports/<name>.md` identities.
Directory-relative, no-follow opens pin the report directory and the leaf;
regular-file and link-count checks occur on the actual opened descriptor.
The file listing uses the same read boundary. Save creates only a new private
file, sanitizes filename components without changing report metadata and never
overwrites an existing leaf/link. Errors do not echo hostile paths or OS details.
Unknown platforms lacking secure directory-relative access fail closed; this
is not a Windows support claim or a general Python sandbox.

Tests: `tests/test_report_file_boundary.py` has 24 cases. Initial result was
23 failed / 1 passed; after repair, those and records/API/SDK compatibility
owners passed together (123 passed). Coverage includes traversals, absolute
and metadata paths, extension/canonical syntax, both link forms, both directory
components, no-create reads, legitimate roundtrip, save collision, leaf exchange,
unsupported secure I/O and a subprocess-bounded FIFO case.

This repairs report file access, not the still-open quote freshness, earnings
event alignment, financial-ratio or future external authorization findings.

# SA Midfill Upgrade Baseline

These are immutable test inputs, not an installed extension or runtime source.
The upgrade and rollback tests need the old collector and old browser package
to prove that existing financial queues survive a version change.

`baseline.zip` contains 25 exact Git blobs from
`b24a2c1dfac740fde8e4b491684b7ff9b58a6b7e`: the collector module and the
24 top-level JS/JSON/CSS/HTML extension files previously loaded with `git show`
and `git ls-tree`. The source commit is provenance only; tests do not resolve
it. The archive remains usable in shallow clones and after history rewriting.

`manifest.json` identifies every path, original Git blob ID, byte length, and
SHA-256 checksum. Loaders verify these before use. Archive entries use a fixed
1980-01-01 timestamp, regular-file mode 0644, and deflate compression. Keeping
the old source archived prevents ordinary code search or test discovery from
treating it as current implementation.

The manifest and archive were compared byte-for-byte with their original Git
blobs before the history rewrite. Any deliberate baseline replacement must
repeat that comparison and the shallow-clone, Firefox, Chromium, upgrade,
and rollback gates. Do not substitute current code for the old baseline.

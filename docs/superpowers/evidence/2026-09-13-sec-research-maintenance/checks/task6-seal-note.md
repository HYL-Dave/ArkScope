# Maintenance Evidence Packaging

The first uncommitted archive candidate selected341 files. Staging checks found
two original task briefs ending with blank lines and the repository's existing
`*.log.*` ignore rule excluding the92 compressed run logs. No commit was made
with this incomplete index.

The candidate directory is preserved in owned scratch as
`maintenance-archive-attempt-01`. The sealer now compresses the two briefs without
editing their original bytes; raw and compressed digests remain in its manifest.
The final archive is generated create-only again. Only its explicitly selected
`*/output.log.gz` files are force-added; no ignore policy is changed and no
scratch, fixture database, credential or binary directory is force-added.

This is archive packaging, not a product/test change, verification rerun or
permission to alter any actual-store state. Commit readback must verify exact
manifest membership as well as both stored and decompressed-source hashes.

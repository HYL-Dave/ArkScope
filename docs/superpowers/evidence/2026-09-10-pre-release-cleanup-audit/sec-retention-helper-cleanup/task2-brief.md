# Task 2: Neutral Canonical Journal Codec

Requirements copied from Task2 of docs/superpowers/plans/2026-09-10-sec-retention-inventory-and-helper-cleanup.md. Base8c8ac738. Parent independently owns the production statistics-only inspection; you have NO production read permission.

Create src/lifecycle_journal_codec.py and tests/test_lifecycle_journal_codec.py. Update exact _json/_sha consumers in old/current journal, adoption/review/history/migration/disposal and their tests. New public functions canonical_json(value, *, ensure_ascii=True) and digest_json(value) preserve exactly json.dumps(sort_keys=True,separators=(",",":"),ensure_ascii=ensure_ascii,allow_nan=False) and hashlib.sha256(canonical_json(value).encode()).hexdigest().

RED first: missing neutral owner/direct current import boundary, literal byte/digest cases for nesting/key sort/compact separators/ASCII escaping/ensure_ascii=False/UTF-8 SHA/rejection NaN and Infinity. Move implementations, update all exact consumers to import new owner directly, remove old definitions/forwarders. Prefer current public names rather than keeping old module aliases. Do not touch unrelated codecs, schema hash algorithms, WebJournalError or its error classification. Preserve actual current/old retained-journal reader behavior.

Baseline and final: affected codec/current store/adoption/review/history/disposal and retained old journal integrity tests. Mutation-check ASCII/separators drift against literal fixture. No test removal other than moved imports/owner; account for node additions. Record commands/intermediate failures and mutation RED/restored GREEN. Commit scoped product/test changes; no docs/plan edits owned by parent.

Run backend through .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py in env -i with PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state and interpreter /home/hyl/.virtualenvs/llm_app/bin/python -B. Unique pytest temp root; no provider/network/prod/.env/App startup/install.

Report in task2-report.md in this same scratch directory: status, exact files/commit range, positive/regression/mutation outputs, accounting, concerns. No subagents. Return only status, commit, high-signal test counts, report path.

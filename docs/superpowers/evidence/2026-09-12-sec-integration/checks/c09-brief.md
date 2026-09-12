# Task8 Independent C09 Leaf Cleanup

Base candidate 88f0512e. Binding authority: pre-release cleanup user decision in
docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/README.md.
Delete abandoned implementations, not current capability or collected data.

Allowed product writes: delete data_sources/{eodhd_source,alpha_vantage_source,
finnhub_source,source_factory}.py, update data_sources/__init__.py; no other
product path. Allowed test writes: tests/test_abandoned_surface_cleanup.py,
tests/test_data_provider_config.py. Allowed current docs: provider catalog,
DESKTOP_APP_VISION_DRAFT, data/IBKR_NEWS_API_LIMITATIONS; do not edit historical
evidence. Report in this plan workspace/c09-report.md. No git index/commit edits.

1. Recheck exact external symbols/consumer graph (no CLI main in these files).
   PolygonDataSource still serves market_data_direct and must remain. Finnhub
   calendar/news collector and current lifecycle EODHD census/key support remain.
2. Add four physical absence owners and package export/import guards, plus
   retained export controls. Run intended assertion RED before deletion, not
   ImportError. Use the existing offline runner and new unique c09-* IDs.
3. Remove only the four modules and obsolete package exports/examples. No alias,
   deprecated stub, new adapter, dependencies or settings changes.
4. Retain direct Polygon Massive-key precedence test; remove its factory arm,
   never the surviving constructor assertion or other key/source tests.
5. Make current docs stop advertising the removed classes/factory, while keeping
   dated API comparisons explicit historical evidence.
6. GREEN cleanup, data-provider configuration, IBKR import safety and lifecycle
   provider census transport suites. Inverses restore a removed leaf/export and
   break retained key/export controls; each must fail its named owner. Restore
   exact source bytes, report commands, real outcomes and changed paths.

No production DB/config/env/token read, live providers, installation, merge,
push, restart or subdelegation. A separate agent builds only SQLite scratch;
Task2 reviewer is read-only on its immutable diff. Other changes are not yours.
This completes C09 only, not C10-C20 or the overall cleanup.

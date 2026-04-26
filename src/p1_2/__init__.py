"""P1.2 free calendar + macro data layer.

Schema lives in ``sql/013_add_p1_2_macro_calendar.sql``; design notes in
``docs/design/P1_2_SPEC.md``. This package only ships the schema +
DAL helpers in commit 1; ingestion jobs, freshness telemetry, and
read API/tools land in later commits.
"""
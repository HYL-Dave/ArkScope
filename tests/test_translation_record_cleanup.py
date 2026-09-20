"""Record cleanup cannot retire translation or alter original research."""

import importlib.util
from pathlib import Path


_CHECKS = (Path(__file__).resolve().parents[1] / "docs/superpowers/evidence/"
           "2026-09-19-card-translation-retirement/checks/test_dispose.py")
_spec = importlib.util.spec_from_file_location("translation_record_cleanup_checks", _CHECKS)
_checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_checks)
TestTranslationRecordCleanup = _checks.DisposalTests

"""Explicit current-article authority for tests of extraction and retry policy.

Membership decisions and unavailable authority use real private stores in
test_sa_article_acquisition_scope and test_sa_comment_acquisition_scope.
"""

import pytest

from src.sa import article_acquisition_scope
from src.tools.backends.sa_capture_backend import SACaptureBackend


@pytest.fixture
def accepted_article_scope(monkeypatch):
    monkeypatch.setattr(SACaptureBackend, "article_acquisition_context", lambda self: {"status":"ok", "context_id":"current-test-fixture"})
    monkeypatch.setattr(article_acquisition_scope, "decide_article_acquisition", lambda *args, **kwargs: {
        "allowed":True, "reason_code":None, "effective_membership":"current", "context_id":"current-test-fixture"})

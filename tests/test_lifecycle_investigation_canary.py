import importlib.util
import json
from pathlib import Path

import pytest


def harness():
    path = Path(__file__).resolve().parents[1] / "docs/superpowers/evidence/2026-09-08-lifecycle-investigation/claude_canary.py"
    spec = importlib.util.spec_from_file_location("investigation_canary_harness", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_calibration_local_fixture_preserves_observation_time_and_full_body(tmp_path):
    from src.lifecycle_investigation.news import LocalNews
    from src.lifecycle_investigation.sources import capture_text
    source = capture_text("Issuer OLD common stock on NASDAQ ceased trading.", url="https://issuer.example/notice",
        retrieved_at="2026-09-07T01:00:00Z", coverage="captured_document", publisher="Issuer")
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"source-1": source}))
    news_path, provenance = harness().seed_local_news(tmp_path, sources_path=path, source_id="source-1", ticker="OLD")
    reader = LocalNews(news_path, None)
    result = reader.search(ticker="OLD")
    captured = reader.read(result["items"][0]["candidate_id"])
    assert captured["text"] == source["text"]
    assert captured["text_sha256"] == source["text_sha256"]
    assert captured["published_at"] == ""
    assert captured["captured_at"] == source["retrieved_at"]
    assert provenance["original_read_at"] == source["retrieved_at"]
    assert provenance["kind"] == "previously_captured_public_source_not_new_provider_observation"
    assert not reader.search(ticker="OTHER")["items"]


def test_live_calibration_rejects_changed_local_fixture_before_creating_corpus(tmp_path):
    from src.lifecycle_investigation.sources import capture_text
    source = capture_text("Original public body.", url="https://issuer.example/notice", retrieved_at="2026-09-07T01:00:00Z", coverage="captured_document")
    source["text"] = "Changed body."
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"source-1": source}))
    with pytest.raises(ValueError, match="local_calibration_source_changed"):
        harness().seed_local_news(tmp_path, sources_path=path, source_id="source-1", ticker="OLD")
    assert not (tmp_path / "captured-local-news.sqlite").exists()

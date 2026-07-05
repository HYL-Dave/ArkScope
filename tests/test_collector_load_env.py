"""Slice B: news collectors resolve the API key os.environ-FIRST.

The sidecar's apply_env() injects DB-managed provider values into os.environ with the
documented precedence (real env > app-DB > config/.env). The collectors' load_env()
used to read config/.env FIRST, which inverted that order: a DB-managed key was
shadowed by the file, so the Settings "test connection" button (os.getenv) and actual
news collection could silently diverge. load_env() must now prefer os.environ and fall
back to reading config/.env directly only for standalone runs that never went through
the env bridge. A placeholder ('your_'-prefixed) or empty env value must NOT shadow a
real key in the file.
"""
from __future__ import annotations

import importlib


def _write_env(tmp_path, key, value):
    cfg = tmp_path / "config"
    cfg.mkdir(exist_ok=True)
    (cfg / ".env").write_text(f"{key}={value}\n")


# --- polygon ---------------------------------------------------------------

def test_polygon_env_wins_over_file(tmp_path, monkeypatch):
    cpn = importlib.import_module("src.collectors.polygon_news")
    _write_env(tmp_path, "POLYGON_API_KEY", "file_key")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("POLYGON_API_KEY", "env_key")  # apply_env injects the DB value here
    assert cpn.load_env() == "env_key"


def test_polygon_falls_back_to_file_when_env_absent(tmp_path, monkeypatch):
    cpn = importlib.import_module("src.collectors.polygon_news")
    _write_env(tmp_path, "POLYGON_API_KEY", "file_key")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    assert cpn.load_env() == "file_key"


def test_polygon_placeholder_env_does_not_shadow_file(tmp_path, monkeypatch):
    cpn = importlib.import_module("src.collectors.polygon_news")
    _write_env(tmp_path, "POLYGON_API_KEY", "file_key")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("POLYGON_API_KEY", "your_key_here")  # stub must not win over a real file key
    assert cpn.load_env() == "file_key"


# --- finnhub ---------------------------------------------------------------

def test_finnhub_env_wins_over_file(tmp_path, monkeypatch):
    cfn = importlib.import_module("src.collectors.finnhub_news")
    _write_env(tmp_path, "FINNHUB_API_KEY", "file_key")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FINNHUB_API_KEY", "env_key")
    assert cfn.load_env() == "env_key"


def test_finnhub_falls_back_to_file_when_env_absent(tmp_path, monkeypatch):
    cfn = importlib.import_module("src.collectors.finnhub_news")
    _write_env(tmp_path, "FINNHUB_API_KEY", "file_key")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    assert cfn.load_env() == "file_key"


def test_finnhub_placeholder_env_does_not_shadow_file(tmp_path, monkeypatch):
    cfn = importlib.import_module("src.collectors.finnhub_news")
    _write_env(tmp_path, "FINNHUB_API_KEY", "file_key")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FINNHUB_API_KEY", "your_key_here")
    assert cfn.load_env() == "file_key"

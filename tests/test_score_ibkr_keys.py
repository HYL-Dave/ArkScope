"""C3c — the batch scorer resolves its OpenAI keys from a scorer-private
config/scoring_keys.txt by DEFAULT (when present), BEFORE falling back to the
OPENAI_API_KEYS / OPENAI_API_KEY env vars. This keeps the scoring key out of the
interactive credential inventory: once it moves to scoring_keys.txt and leaves
OPENAI_API_KEYS, a default scorer run must NOT silently fall back to the (now
different) OPENAI_API_KEY account. Hermetic: temp files + a fake env, FAKE keys.
"""

from __future__ import annotations

from pathlib import Path

from scripts.scoring.score_ibkr_news import resolve_scoring_keys


def _write(p: Path, *lines: str) -> Path:
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_explicit_api_keys_file_wins(tmp_path):
    f = _write(tmp_path / "explicit.txt", "sk-explicit1", "sk-explicit2")
    scoring = _write(tmp_path / "scoring_keys.txt", "sk-scoring1")
    keys, source = resolve_scoring_keys(
        api_keys_file=str(f), scoring_keys_path=scoring,
        env={"OPENAI_API_KEY": "sk-env1"},
    )
    assert keys == ["sk-explicit1", "sk-explicit2"] and source == "api-keys-file"


def test_explicit_api_key_wins_over_defaults(tmp_path):
    scoring = _write(tmp_path / "scoring_keys.txt", "sk-scoring1")
    keys, source = resolve_scoring_keys(
        api_key="sk-flagkey", scoring_keys_path=scoring,
        env={"OPENAI_API_KEYS": "sk-env1,sk-env2"},
    )
    assert keys == ["sk-flagkey"] and source == "api-key"


def test_scoring_keys_file_default_beats_env(tmp_path):
    # THE regression: no flags, scoring_keys.txt present → keys come from the FILE,
    # not from OPENAI_API_KEY / OPENAI_API_KEYS.
    scoring = _write(tmp_path / "scoring_keys.txt", "sk-scoringA", "sk-scoringB")
    keys, source = resolve_scoring_keys(
        scoring_keys_path=scoring,
        env={"OPENAI_API_KEY": "sk-wrongaccount", "OPENAI_API_KEYS": "sk-wrong1,sk-wrong2"},
    )
    assert keys == ["sk-scoringA", "sk-scoringB"] and source == "scoring_keys.txt"
    assert "sk-wrongaccount" not in keys


def test_falls_back_to_openai_api_keys_when_no_file(tmp_path):
    keys, source = resolve_scoring_keys(
        scoring_keys_path=tmp_path / "absent.txt",
        env={"OPENAI_API_KEYS": "sk-a,sk-b", "OPENAI_API_KEY": "sk-single"},
    )
    assert keys == ["sk-a", "sk-b"] and source == "OPENAI_API_KEYS"


def test_falls_back_to_single_key_last(tmp_path):
    keys, source = resolve_scoring_keys(
        scoring_keys_path=tmp_path / "absent.txt",
        env={"OPENAI_API_KEY": "sk-single"},
    )
    assert keys == ["sk-single"] and source == "OPENAI_API_KEY"


def test_none_when_nothing(tmp_path):
    keys, source = resolve_scoring_keys(scoring_keys_path=tmp_path / "absent.txt", env={})
    assert keys == [] and source == "none"


def test_scoring_file_strips_and_drops_blanks(tmp_path):
    scoring = _write(tmp_path / "scoring_keys.txt", "sk-a ", "", "  ", "sk-b")
    keys, source = resolve_scoring_keys(scoring_keys_path=scoring, env={})
    assert keys == ["sk-a", "sk-b"] and source == "scoring_keys.txt"


def test_scoring_path_that_is_a_directory_falls_through(tmp_path):
    # a path that exists but is NOT a regular file (dir / unreadable) must fall
    # through to env, not crash on open() — guard with is_file(), not exists().
    d = tmp_path / "scoring_keys.txt"
    d.mkdir()
    keys, source = resolve_scoring_keys(scoring_keys_path=d, env={"OPENAI_API_KEY": "sk-env1"})
    assert keys == ["sk-env1"] and source == "OPENAI_API_KEY"


def test_default_path_resolves_to_project_root(tmp_path, monkeypatch):
    # exercise the IMPLICIT defaults main() relies on: scoring_keys_path=None ->
    # PROJECT_ROOT/config/scoring_keys.txt, env=None -> live os.environ.
    import scripts.scoring.score_ibkr_news as m

    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    (tmp_path / "config").mkdir()
    _write(tmp_path / "config" / "scoring_keys.txt", "sk-fromfile1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fromenv1")
    keys, source = m.resolve_scoring_keys()  # no args → both defaults
    assert keys == ["sk-fromfile1"] and source == "scoring_keys.txt"  # default path beats live env


def test_whole_quoted_pool_env_fallback(tmp_path):
    # the OPENAI_API_KEYS fallback must also unwrap a whole-value-quoted pool
    # before splitting (parity with the credential importer's _split_key_pool).
    keys, source = resolve_scoring_keys(
        scoring_keys_path=tmp_path / "absent.txt",
        env={"OPENAI_API_KEYS": '"sk-a,sk-b"'},
    )
    assert keys == ["sk-a", "sk-b"] and source == "OPENAI_API_KEYS"  # no boundary quotes


def test_default_env_used_when_no_default_file(tmp_path, monkeypatch):
    import scripts.scoring.score_ibkr_news as m

    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)  # no config/scoring_keys.txt here
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fromenv2")
    monkeypatch.delenv("OPENAI_API_KEYS", raising=False)
    keys, source = m.resolve_scoring_keys()  # env=None binds to live os.environ
    assert keys == ["sk-fromenv2"] and source == "OPENAI_API_KEY"

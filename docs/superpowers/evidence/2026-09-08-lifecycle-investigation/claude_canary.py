"""Explicit authorized OAuth calibration; isolated journal and no profile actions."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))


def metadata(profile):
    with sqlite3.connect(profile.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT id,provider,auth_type,active,updated_at,expires_at FROM llm_credentials "
            "WHERE provider='anthropic' AND auth_type='claude_code_oauth' AND active=1").fetchall()
        if len(rows) != 1:
            raise ValueError("active_claude_oauth_ambiguous")
        return dict(rows[0])


def seed_local_news(work, *, sources_path, source_id, ticker):
    from src.lifecycle_investigation.sources import capture_text
    from src.news_normalized.schema import ARTICLE_SCHEMA
    if (sources_path is None) != (source_id is None):
        raise ValueError("local_calibration_source_required")
    if sources_path is None:
        return None, None
    raw = sources_path.read_bytes()
    original = json.loads(raw)[source_id]
    source = capture_text(**{key: value for key, value in original.items() if key != "text_sha256"})
    if source["text_sha256"] != original["text_sha256"]:
        raise ValueError("local_calibration_source_changed")
    path = work / "captured-local-news.sqlite"
    with sqlite3.connect(path) as conn:
        conn.executescript(ARTICLE_SCHEMA)
        # The normalized corpus requires a string; do not invent an unobserved publication date.
        conn.execute("INSERT INTO news_articles(id,source,canonical_title,publisher,url,published_at,content_kind,created_at,updated_at) "
            "VALUES(1,'public_calibration',?,?,?,?, 'full_text',?,?)", (source["title"] or "Captured public document", source["publisher"],
                source["url"], source["published_at"] or "", source["retrieved_at"], source["retrieved_at"]))
        conn.execute("INSERT INTO news_article_tickers VALUES(1,?,'primary',?,?)", (ticker, source["retrieved_at"], source["retrieved_at"]))
        conn.execute("INSERT INTO news_article_bodies(article_id,body_status,body_text,fetched_at) VALUES(1,'fetched',?,?)", (source["text"], source["retrieved_at"]))
    return path, {"kind": "previously_captured_public_source_not_new_provider_observation", "source_id": source_id,
        "input_file_sha256": hashlib.sha256(raw).hexdigest(), "text_sha256": source["text_sha256"], "original_read_at": source["retrieved_at"]}


def execute(profile, work, ticker, issuer, model, *, local_sources=None, local_source_id=None):
    from claude_agent_sdk import ClaudeSDKClient, SystemMessage, ResultMessage, RateLimitEvent
    from src.auth_drivers import lifecycle_web_claude
    from src.auth_drivers.lifecycle_web_models import credential_generation, resolve_web_credential
    from src.auth_drivers.token_store import get_token_store
    from src.lifecycle_investigation.controller import InvestigationController
    from src.lifecycle_investigation.news import LocalNews
    from src.lifecycle_investigation.runtime import InvestigationRuntime
    from src.lifecycle_investigation.schema import install_journal
    from src.lifecycle_investigation.sources import InvestigationSourceReader
    from src.lifecycle_investigation.store import InvestigationStore
    from src.lifecycle_investigation.target import Target
    from src.lifecycle_web_sec_sources import SecSourcePolicy
    from src.security_lifecycle_schema import create_profile_schema
    from src.security_lifecycle_web_contract import validate_selection

    if work.exists() or not any(work.resolve().is_relative_to(base) for base in (Path("/tmp"), Path("/dev/shm"))):
        raise ValueError("new_temporary_directory_required")
    os.umask(0o077)
    work.mkdir(mode=0o700)
    local_path, local_provenance = seed_local_news(work, sources_path=local_sources, source_id=local_source_id, ticker=ticker)
    code_paths = sorted({*ROOT.glob("src/lifecycle_investigation/*.py"),
        *ROOT.glob("src/auth_drivers/*.py"), *ROOT.glob("src/lifecycle_*.py"),
        ROOT / "src/security_lifecycle_web_finding.py", Path(__file__).resolve()})
    manifest = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in code_paths}
    (work / "execution-source-manifest.json").write_text(json.dumps(manifest, indent=2))
    selected_row = metadata(profile)
    selection = validate_selection("anthropic", "claude_code_oauth", model, f"local:{selected_row['id']}")
    observations = {"sdk_submissions": 0, "token_loads": 0, "init": [], "results": [], "rate_limits": [], "local_fixture": local_provenance,
        "authority": "2026-09-08 user preauthorized Claude OAuth freely; no other billing channel",
        "production_writes": False, "profile_actions": False, "fallback": False,
        "execution_source_manifest_sha256": hashlib.sha256((work / "execution-source-manifest.json").read_bytes()).hexdigest()}
    private_values = []

    class Credentials:
        def get(self, identity):
            if identity != selection.credential_id or metadata(profile) != selected_row:
                raise ValueError("selected_credential_changed")
            return SimpleNamespace(**selected_row, secret=None)

    backend = get_token_store(dev_path=os.environ.get("ARKSCOPE_TOKEN_STORE_PATH") or profile.parent / "auth_tokens.json")
    class Tokens:
        def load(self, **kwargs):
            if observations["token_loads"] or kwargs != {"provider": selection.provider, "auth_mode": selection.auth_mode, "credential_id": selection.credential_id}:
                raise ValueError("selected_credential_changed")
            observations["token_loads"] += 1
            record = backend.load(**kwargs)
            if record:
                private_values.extend(value for value in (record.access_token, record.refresh_token) if value)
            return record

    class ObservedClient(ClaudeSDKClient):
        async def query(self, prompt, **kwargs):
            observations["sdk_submissions"] += 1
            print(json.dumps({"sdk_submission": observations["sdk_submissions"]}), flush=True)
            return await super().query(prompt, **kwargs)

        async def receive_response(self):
            async for message in super().receive_response():
                if isinstance(message, SystemMessage) and message.subtype == "init":
                    data = message.data or {}
                    observations["init"].append({"api_key_source": data.get("apiKeySource", "absent"),
                        "model": data.get("model"), "tools": data.get("tools"),
                        "mcp_server_count": len(data.get("mcp_servers", []))})
                if isinstance(message, ResultMessage):
                    observations["results"].append({"subtype": message.subtype, "is_error": message.is_error,
                        "num_turns": message.num_turns, "model_usage": message.model_usage})
                if isinstance(message, RateLimitEvent):
                    observations["rate_limits"].append({field: getattr(message.rate_limit_info, field, None)
                        for field in ("status", "rate_limit_type", "utilization", "resets_at")})
                yield message

    with sqlite3.connect(profile.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        row = conn.execute("SELECT value FROM data_provider_config WHERE provider='sec_edgar' AND field='user_agent'").fetchone()
        contact = row[0] if row else ""
    class Reader(InvestigationSourceReader):
        def __init__(self, limits):
            super().__init__(limits, sec_policy=SecSourcePolicy(user_agent=contact))

    at = datetime.now(timezone.utc).isoformat()
    target = Target(ticker=ticker, issuer_name=issuer, security_class="common stock", venue="NASDAQ", as_of=at[:10])
    runtime = InvestigationRuntime()
    binding = {"version": 2, "language": "zh-Hant", "target": target.model_dump(), "selection": asdict(selection),
        "runtime": runtime.model_dump(), "effort": "high", "credential_generation": credential_generation(SimpleNamespace(**selected_row, secret=None)),
        "provider_observations": {"listings": [], "observed_at": None, "gaps": ["structured_check_missing"]}, "provider_sha256": None}
    path = work / "profile.sqlite"
    with sqlite3.connect(path) as conn:
        create_profile_schema(conn)
        conn.commit()
        install_journal(conn, at=at)
    original = lifecycle_web_claude._client
    lifecycle_web_claude._client = lambda options: ObservedClient(options=options)
    store = InvestigationStore(path)
    controller = InvestigationController(store, credential_loader=lambda selected: resolve_web_credential(selected,
        store=Credentials(), token_store=Tokens()), news_factory=lambda: LocalNews(local_path or work / "no-local-corpus.db", None), reader_factory=Reader)
    try:
        job = controller.start(binding=binding, request_key="authorized-canary")
        run_id = job["run_id"]
        phase = None
        while controller.is_local_running(run_id):
            value = controller.read(run_id)
            if value["phase"] != phase:
                phase = value["phase"]
                print(json.dumps({"phase": phase, "stats": value["stats"]}), flush=True)
            time.sleep(1)
        result = controller.read(run_id)
        raw = store.read(run_id)
        outputs = {"result.json": result, "observations.json": observations,
            "steps.json": raw["steps"], "sources.json": raw["sources"], "calls.json": raw["calls"]}
        for name, value in outputs.items():
            serialized = json.dumps(value, ensure_ascii=False, indent=2)
            if any(secret in serialized for secret in private_values):
                raise ValueError("secret_in_evidence")
            (work / name).write_text(serialized)
        print(json.dumps({"work": str(work), "status": result["status"], "failure_code": result["failure_code"],
            "stop_reason": result["stop_reason"], "action": result["action"], "block_reasons": result["block_reasons"],
            "stats": result["stats"], "sdk_submissions": observations["sdk_submissions"]}, ensure_ascii=False), flush=True)
    finally:
        controller.close()
        lifecycle_web_claude._client = original


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--ticker", choices=("TA", "SMCI"), required=True)
    parser.add_argument("--model", choices=("claude-sonnet-5", "claude-opus-5"), default="claude-sonnet-5")
    parser.add_argument("--local-sources", type=Path)
    parser.add_argument("--local-source-id")
    parser.add_argument("--execute", action="store_true", required=True)
    args = parser.parse_args()
    issuer = {"TA": "TravelCenters of America Inc.", "SMCI": "Super Micro Computer, Inc."}[args.ticker]
    execute(args.profile, args.work, args.ticker, issuer, args.model, local_sources=args.local_sources, local_source_id=args.local_source_id)

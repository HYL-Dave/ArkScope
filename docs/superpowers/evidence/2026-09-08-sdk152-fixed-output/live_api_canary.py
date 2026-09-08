"""One source-bound Luna API-key translation. No refresh, retry, or DB write."""

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sqlite3
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

MODEL = "gpt-5.6-luna"
SCHEMA = {"type": "object", "additionalProperties": False,
          "properties": {"translated_text": {"type": "string"}},
          "required": ["translated_text"]}


def run(profile, credential_id, output):
    import httpx
    from openai import OpenAI
    from src import card_synthesis as cs
    from src.auth_drivers.live_resolver import LiveAuthResolution

    evidence = {"started_at": datetime.now(timezone.utc).isoformat(),
                "channel": "api_key", "requested_model": MODEL, "effort": "low",
                "status": "not_started", "requests": [], "request_budget": 1,
                "profile_writes": False, "token_writes": False}
    started = time.monotonic()
    with output.open("x", encoding="utf-8") as report:
        try:
            with sqlite3.connect(profile.resolve().as_uri() + "?mode=ro", uri=True) as conn:
                conn.execute("PRAGMA query_only=ON")
                row = conn.execute("SELECT provider,auth_type,secret FROM llm_credentials WHERE id=?",
                                   (credential_id,)).fetchone()
            if row is None or row[:2] != ("openai", "api_key") or not row[2]:
                raise ValueError("credential_selection_mismatch")

            class OneRequest(httpx.HTTPTransport):
                def handle_request(self, request):
                    body = json.loads(request.content)
                    if (evidence["requests"] or request.method != "POST"
                            or str(request.url) != "https://api.openai.com/v1/responses"
                            or body.get("model") != MODEL
                            or body.get("reasoning") != {"effort": "low"}
                            or request.headers.get("authorization") != "Bearer " + row[2]):
                        raise RuntimeError("request_budget_or_identity_changed")
                    receipt = {"method": "POST", "host": "api.openai.com", "path": "/v1/responses"}
                    evidence["requests"].append(receipt)
                    response = super().handle_request(request)
                    receipt["http_status"] = response.status_code
                    response.read()
                    if response.status_code == 200:
                        data = json.loads(response.content)
                        evidence["observed_model"] = data.get("model")
                        usage = data.get("usage") or {}
                        evidence["usage"] = {key: usage.get(key) for key in
                                             ("input_tokens", "output_tokens", "total_tokens")}
                    return response

            with OpenAI(api_key=row[2], base_url="https://api.openai.com/v1", max_retries=0, timeout=90,
                        http_client=httpx.Client(transport=OneRequest(retries=0))) as client:
                with patch("src.auth_drivers.live_resolver.resolve_live_auth",
                           return_value=LiveAuthResolution("openai", "db_api_key", f"local:{credential_id}")), \
                     patch("src.auth_drivers.live_resolver.live_openai_client", return_value=client):
                    result = cs._translate_openai(
                        MODEL, "Translate into English. Call emit_translation exactly once.",
                        "Revenue increased.", SCHEMA, "English", effort="low", model_timeout_s=90)
            if result != {"translated_text": "Revenue increased."}:
                raise ValueError("translation_validation_failed")
            evidence["status"] = "passed"
        except Exception as error:
            evidence["status"] = "failed"
            evidence["error_type"] = type(error).__name__
            evidence["http_status"] = getattr(error, "status_code", None)
        finally:
            evidence["elapsed_s"] = round(time.monotonic() - started, 3)
            json.dump(evidence, report, indent=2)
            print(json.dumps(evidence), flush=True)
    return evidence["status"] == "passed"


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--credential-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if run(args.profile, args.credential_id, args.output) else 1)

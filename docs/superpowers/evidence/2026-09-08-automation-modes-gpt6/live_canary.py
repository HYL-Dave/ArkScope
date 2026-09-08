"""Explicit, one-request canary using a pinned existing credential, no DB writes.

Run each channel once. No discovery, token refresh, retries or fallback. Only a
synthetic sentence leaves the machine; output contains no provider body/secrets.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))


def execute(channel, profile, credential_id, output):
    import httpx
    from openai import AsyncOpenAI, OpenAI
    from src import card_synthesis as cs
    from src.auth_drivers import subscription_structured_output as sub
    from src.auth_drivers.chatgpt_oauth_login import refresh_if_needed
    from src.auth_drivers.live_resolver import LiveAuthResolution
    from src.auth_drivers.oauth_status import OAuthObservationStore
    from src.auth_drivers.token_store import get_token_store

    model = "gpt-6-astra" if channel == "api_key" else "gpt-5.6-luna"
    observation = {"channel": channel, "requested_model": model, "effort": "low",
                   "started_at": datetime.now(timezone.utc).isoformat(), "requests": [],
                   "status": "not_started", "profile_writes": False, "token_writes": False}
    schema = {"type": "object", "additionalProperties": False,
              "properties": {"translated_text": {"type": "string"}}, "required": ["translated_text"]}
    system = "Translate into English. Respond only by calling emit_translation exactly once."
    user = '{"text":"Revenue increased."}'
    with output.open("x", encoding="utf-8") as report, tempfile.TemporaryDirectory(prefix="arkscope_canary_") as work:
        started = time.monotonic()
        client = None
        try:
            with sqlite3.connect(profile.resolve().as_uri() + "?mode=ro", uri=True) as conn:
                conn.execute("PRAGMA query_only=ON")
                row = conn.execute("SELECT provider,auth_type,secret,active FROM llm_credentials WHERE id=?", (credential_id,)).fetchone()
            if row is None or row[:2] != ("openai", channel):
                raise ValueError("credential_selection_mismatch")
            identity = f"local:{credential_id}"
            host = "api.openai.com" if channel == "api_key" else "chatgpt.com"
            path = "/v1/responses" if channel == "api_key" else "/backend-api/codex/responses"

            def count(request):
                body = json.loads(request.content)
                if observation["requests"] or request.method != "POST" or request.url.host != host or request.url.path != path or body["model"] != model:
                    raise RuntimeError("request_budget_or_selection_changed")
                item = {"method": request.method, "host": host, "path": path, "model": body["model"]}
                observation["requests"].append(item)
                return item

            if channel == "api_key":
                if not row[2]:
                    raise ValueError("missing_selected_key")

                class CountedTransport(httpx.HTTPTransport):
                    def handle_request(self, request):
                        item = count(request)
                        response = super().handle_request(request)
                        item["http_status"] = response.status_code
                        response.read()
                        if response.status_code == 200:
                            data = json.loads(response.content)
                            observation["observed_model"] = data.get("model")
                            observation["usage"] = data.get("usage")
                        return response

                client = OpenAI(api_key=row[2], base_url="https://api.openai.com/v1", max_retries=0,
                                timeout=90, http_client=httpx.Client(transport=CountedTransport(retries=0)))
                with patch("src.auth_drivers.live_resolver.resolve_live_auth", return_value=LiveAuthResolution("openai", "db_api_key", identity)), \
                     patch("src.auth_drivers.live_resolver.live_openai_client", return_value=client):
                    payload = cs._translate_openai(model, system, user, schema, "English", effort="low", model_timeout_s=90)
            else:
                if not row[3]:
                    raise ValueError("selected_oauth_not_active")
                store = get_token_store(dev_path=profile.parent / "auth_tokens.json")
                record = store.load(provider="openai", auth_mode=channel, credential_id=identity)

                class ReadOnlyTokens:
                    def load(self, **kwargs):
                        if kwargs != {"provider": "openai", "auth_mode": channel, "credential_id": identity}:
                            raise ValueError("token_selection_mismatch")
                        return record

                    def save(self, **kwargs):
                        raise RuntimeError("token_write_forbidden")

                def no_refresh(**kwargs):
                    raise RuntimeError("refresh_not_in_canary_budget")

                def refresh_selected(**kwargs):
                    return refresh_if_needed(**kwargs, refresh=no_refresh,
                        observation_store=OAuthObservationStore(Path(work) / "observations.db"))

                class CountedTransport(httpx.AsyncHTTPTransport):
                    async def handle_async_request(self, request):
                        item = count(request)
                        response = await super().handle_async_request(request)
                        item["http_status"] = response.status_code
                        return response

                def make_client(token, base_url, timeout_s):
                    result = AsyncOpenAI(api_key=token, base_url=base_url, timeout=timeout_s, max_retries=0,
                                         http_client=httpx.AsyncClient(transport=CountedTransport(retries=0)))
                    original = result.responses.create

                    async def observed_create(**kwargs):
                        stream = await original(**kwargs)

                        class ObservedStream:
                            async def __aiter__(self):
                                async for event in stream:
                                    if event.type == "response.completed":
                                        observation["observed_model"] = event.response.model
                                        observation["usage"] = event.response.usage.model_dump() if event.response.usage else None
                                    yield event

                            async def close(self):
                                await stream.close()

                        return ObservedStream()

                    result.responses.create = observed_create
                    return result

                with patch.object(sub, "_openai_client", make_client), patch.object(sub, "_refresh_chatgpt_token", refresh_selected):
                    payload = sub.run_subscription_structured_output(
                        task="card_translation", provider="openai", auth_mode=channel, credential_id=identity,
                        model=model, system=system, user=user, output_name="emit_translation",
                        output_description="Emit the English translation.", schema=schema, effort="low",
                        token_store=ReadOnlyTokens(), timeout_s=90)
            if set(payload) != {"translated_text"} or payload["translated_text"] != "Revenue increased.":
                raise ValueError("translation_validation_failed")
            observed = observation.get("observed_model")
            if observed != model and not (isinstance(observed, str) and observed.startswith(model + "-")):
                raise ValueError("observed_model_mismatch")
            observation["status"] = "passed"
        except Exception as error:
            observation["status"] = "failed"
            observation["error_type"] = type(error).__name__
            observation["http_status"] = getattr(error, "status_code", None)
        finally:
            if client is not None:
                client.close()
            observation["elapsed_s"] = round(time.monotonic() - started, 3)
            json.dump(observation, report, indent=2)
            print(json.dumps(observation), flush=True)
    return observation["status"] == "passed"


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", choices=("api_key", "chatgpt_oauth"), required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--credential-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if execute(args.channel, args.profile, args.credential_id, args.output) else 1)

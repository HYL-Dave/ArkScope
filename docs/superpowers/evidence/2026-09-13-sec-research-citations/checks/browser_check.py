"""Real temporary API/store citation reopening through the Research drawer."""

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch
from urllib.parse import urlsplit

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WORK))

# Reuse the unchanged production/network/CLI audit guard before product imports.
import offline_pytest  # noqa: F401, E402

STATE = Path(os.environ["ARKSCOPE_OFFLINE_TEST_WORKSPACE"]) / "state"
STATE.mkdir(parents=True, exist_ok=True)
for name, leaf in {
    "ARKSCOPE_PROFILE_DB": "profile.db", "ARKSCOPE_MARKET_DB": "market.db",
    "ARKSCOPE_SA_DB": "sa.db", "ARKSCOPE_MACRO_CALENDAR_DB": "macro.db",
    "ARKSCOPE_TOKEN_STORE_PATH": "tokens.json", "ARKSCOPE_LOCK_DIR": "locks",
}.items():
    os.environ[name] = str(STATE / leaf)
from src import env_keys  # noqa: E402
env_keys._loaded = True

from browser_fixture import fixture_app  # noqa: E402
from playwright.sync_api import expect, sync_playwright  # noqa: E402


def check_layout(page):
    geometry = page.evaluate("""() => ({
      width: innerWidth,
      scrollWidth: document.scrollingElement.scrollWidth,
      clippedButtons: [...document.querySelectorAll('button')].filter(el => {
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0 &&
          (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1);
      }).map(el => el.getAttribute('aria-label') || el.textContent)
    })""")
    assert geometry["scrollWidth"] <= geometry["width"], geometry
    assert not geometry["clippedButtons"], geometry
    return geometry


def exercise(base, output, *, prepare_only=False):
    from src.api.dependencies import get_run_store, get_thread_store
    from src.api.routes import query, research
    from src.research_runs import ResearchRunStore
    from src.research_threads import ResearchThreadStore
    from src.sec_research.citations import citation_event_fields, read_sec_citation
    from src.sec_research.captures import CaptureStore
    from src.sec_research.paths import SecResearchPaths
    from src.sec_research.store import Store

    output.mkdir(parents=True, exist_ok=False)
    results = []
    with fixture_app(output.parent / "api-store") as (client, state, initial_paths):
        state["fail_history"] = False
        cik = "0000320193"
        refresh = client.post(f"/sec-research/{cik}/refresh", json={"max_sources": 4})
        assert refresh.status_code == 200 and refresh.json()["status"] == "ok", refresh.text
        filings = client.get(f"/sec-research/{cik}/filings?limit=1").json()
        filing_id = filings["data"][0]["filing_id"]
        acquired = client.post(f"/sec-research/filings/{filing_id}/document", json={"document_id": "primary"})
        assert acquired.status_code == 200, acquired.text
        document = client.get(f"/sec-research/filings/{filing_id}/document?query=needle&max_chars=160").json()
        facts = client.get(f"/sec-research/{cik}/facts?limit=1").json()
        envelopes = [("read_sec_filing", document), ("get_sec_financial_facts", facts), ("list_sec_filings", filings)]
        calls = [{"name": name, "call_id": f"browser-{index}", "input": {},
                  "result_preview": "Stored SEC evidence", **citation_event_fields(name, envelope)}
                 for index, (name, envelope) in enumerate(envelopes)]
        assert all(call.get("sec_citations") for call in calls), calls
        pinned = calls[0]["sec_citations"][0]
        expected_text = read_sec_citation(Store(initial_paths), CaptureStore(Store(initial_paths), budget=lambda: 1), citation=pinned)["data"]["text"]
        assert "Caf\u00e9 \u8ca1\u5831" in expected_text and "needle 1" in expected_text

        profile = output.parent / "api-store/profile.db"
        threads, runs = ResearchThreadStore(profile), ResearchRunStore(profile)
        threads.ensure_thread(id="citation-browser", title="SEC retained evidence")
        runs.create_run(id="citation-browser-run", thread_id="citation-browser", question="Read SEC evidence",
                        ticker=None, provider="openai", model="offline-fixture", effort="low",
                        auth_mode=None, credential_id=None)
        for call in calls:
            runs.append_event("citation-browser-run", "tool_end", {"tool": call["name"],
                "summary": call["result_preview"],
                **{key: value for key, value in call.items() if key != "name" and key != "result_preview"}})
        saved_events = ResearchRunStore(profile).list_events("citation-browser-run")
        query._persist_assistant_turn(threads, thread_id="citation-browser", run_id="citation-browser-run",
            done_data={"answer": "Retained SEC source observations", "provider": "openai", "model": "offline-fixture"},
            collected=[(event.type, event.data) for event in saved_events], elapsed=1)
        runs.mark_terminal("citation-browser-run", "succeeded")
        client.app.include_router(research.router)
        client.app.dependency_overrides[get_thread_store] = lambda: threads
        client.app.dependency_overrides[get_run_store] = lambda: runs
        current_paths = initial_paths
        observed = []

        # Advance the source, then move only these generated closed stores.
        state["document_revision"] = 2
        newer = client.post(f"/sec-research/filings/{filing_id}/document", json={"document_id": "primary"})
        assert newer.status_code == 200, newer.text
        newest = client.get(f"/sec-research/filings/{filing_id}/document?query=needle&max_chars=160").json()
        newest_ref = citation_event_fields("read_sec_filing", newest)["sec_citations"][0]
        assert newest_ref["capture_id"] != pinned["capture_id"]
        assert read_sec_citation(Store(initial_paths), CaptureStore(Store(initial_paths), budget=lambda: 1),
                                 citation=pinned)["data"]["text"] == expected_text
        moved_dir = output.parent / "relocated"
        moved_dir.mkdir()
        moved_market = moved_dir / "research-market.db"
        for suffix in ("", "-wal", "-shm"):
            source = Path(str(initial_paths.market_db_path) + suffix)
            if source.exists():
                shutil.move(source, Path(str(moved_market) + suffix))
        current_paths = SecResearchPaths.from_market_db(moved_market)
        shutil.move(initial_paths.capture_root, current_paths.capture_root)
        assert not initial_paths.market_db_path.exists() and not initial_paths.capture_root.exists()
        assert read_sec_citation(Store(current_paths), CaptureStore(Store(current_paths), budget=lambda: 1),
                                 citation=pinned)["data"]["text"] == expected_text

        def message():
            # Read the persisted message, not an in-memory citation fixture.
            row = threads.list_messages("citation-browser")[-1]
            return {"role": row.role, "content": row.content, "tool_calls": row.tool_calls,
                    "tools_used": row.tools_used, "tickers": row.tickers, "created_at": row.created_at,
                    "runId": row.run_id, "provider": row.provider, "model": row.model}

        if prepare_only:
            assert message()["tool_calls"] == calls
            record = {"phase": "fixture_setup_only", "calls": len(calls),
                      "references": sum(len(call["sec_citations"]) for call in calls),
                      "passage_utf8_bytes": len(expected_text.encode("utf-8")),
                      "source_dispatches": len(state["source_dispatches"]),
                      "document_dispatches": len(state["document_dispatches"]),
                      "newer_capture_distinct": newest_ref["capture_id"] != pinned["capture_id"],
                      "reopened_after_relocation": True,
                      "browser_exercised": False}
            (output / "results.json").write_text(json.dumps(record, indent=2))
            print(json.dumps(record))
            return

        def route_request(route):
            parsed = urlsplit(route.request.url)
            if parsed.path == "/fixture/message":
                route.fulfill(status=200, json=message())
                return
            assert parsed.path.startswith("/api/"), parsed.path
            assert parsed.path in {"/api/sec-research/citation", "/api/research/runs/citation-browser-run"}, parsed.path
            path = parsed.path[4:] + ("?" + parsed.query if parsed.query else "")
            assert route.request.method == "GET", route.request.method
            with patch.object(SecResearchPaths, "resolve", lambda: current_paths):
                response = client.get(path)
            body = response.json()
            observed.append({"path": path, "status": response.status_code, "body": body})
            route.fulfill(status=response.status_code, json=body)

        with sync_playwright() as playwright:
            dispatches_before = (len(state["source_dispatches"]), len(state["document_dispatches"]), len(state["writes"]))
            browser = playwright.chromium.launch(headless=True)
            try:
                for locale in ("en", "zh-Hant"):
                    for width in (1280, 390):
                        context = browser.new_context(viewport={"width": width, "height": 900})
                        page = context.new_page()
                        page.route("**/api/**", route_request)
                        page.route("**/fixture/message", route_request)
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        page.goto(f"{base}/?locale={locale}")
                        page.get_by_role("button", name="Open evidence", exact=True).click()
                        close_label = "Close SEC source" if locale == "en" else "\u95dc\u9589 SEC \u4f86\u6e90"
                        retry_label = "Retry SEC source" if locale == "en" else "\u91cd\u8a66 SEC \u4f86\u6e90"
                        document_trigger = page.locator('[data-sec-citation-open="0:0"]')
                        document_trigger.click()
                        source = page.locator('[data-sec-citation-view="document"]')
                        expect(source.locator(".sec-citation-text")).to_have_text(expected_text)
                        assert source.locator(".sec-citation-text").text_content() == expected_text
                        expect(source.get_by_role("button", name=close_label, exact=True)).to_be_focused()
                        assert "needle 2" not in source.inner_text()
                        geometry = check_layout(page)
                        page.screenshot(path=output / f"{locale}-{width}-document.png", full_page=True)
                        source.get_by_role("button", name=close_label, exact=True).click()
                        expect(source).to_have_count(0)
                        expect(document_trigger).to_be_focused()

                        # Exact fact/filing reads use the same saved references.
                        page.locator('[data-sec-citation-open="1:0"]').click()
                        fact_source = page.locator('[data-sec-citation-view="fact"]')
                        expect(fact_source).to_contain_text(facts["data"][0]["value"])
                        expect(fact_source).to_contain_text(facts["data"][0]["end"])
                        check_layout(page)
                        fact_source.get_by_role("button", name=close_label, exact=True).click()
                        page.locator('[data-sec-citation-open="2:0"]').click()
                        filing_source = page.locator('[data-sec-citation-view="filing"]')
                        expect(filing_source).to_contain_text("2026-06-30")
                        expect(filing_source).to_contain_text(filings["data"][0]["primary_document"])
                        check_layout(page)
                        filing_source.get_by_role("button", name=close_label, exact=True).click()

                        # Damage only this generated object's availability, then restore it.
                        original = current_paths.object_path("objects/" + pinned["original_sha256"])
                        held = output.parent / "held-fixture-object"
                        shutil.move(original, held)
                        try:
                            document_trigger.click()
                            expect(source).to_contain_text("sec_citation_integrity_failed")
                            expect(source.locator(".sec-citation-text")).to_have_count(0)
                        finally:
                            shutil.move(held, original)
                        source.get_by_role("button", name=retry_label, exact=True).click()
                        expect(source.locator(".sec-citation-text")).to_have_text(expected_text)
                        assert source.locator(".sec-citation-text").text_content() == expected_text
                        source.get_by_role("button", name=close_label, exact=True).focus()
                        page.keyboard.press("Escape")
                        expect(source).to_have_count(0)
                        expect(document_trigger).to_be_focused()

                        # Reload the actual persisted message, with original paths gone.
                        page.keyboard.press("Escape")
                        expect(page.get_by_role("button", name="Open evidence", exact=True)).to_be_focused()
                        page.get_by_role("button", name="Reload saved turn", exact=True).click()
                        expect(page.locator("main")).to_have_attribute("data-fixture-load", "2")
                        page.get_by_role("button", name="Open evidence", exact=True).click()
                        document_trigger.click()
                        expect(source.locator(".sec-citation-text")).to_have_text(expected_text)
                        assert source.locator(".sec-citation-text").text_content() == expected_text
                        assert not errors, errors
                        results.append({"locale": locale, "width": width, "geometry": geometry,
                                        "pinned_text": expected_text, "newer_capture_distinct": True,
                                        "reopened_after_relocation": True, "persisted_message_reloaded": True,
                                        "exact_fact_value": facts["data"][0]["value"],
                                        "missing_object_retry": True, "focus_restored": True,
                                        "page_errors": errors})
                        context.close()
            finally:
                browser.close()
            assert dispatches_before == (len(state["source_dispatches"]), len(state["document_dispatches"]), len(state["writes"]))
        (output / "results.json").write_text(json.dumps({"workflows": results, "responses": observed}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    exercise(args.base, args.output, prepare_only=args.prepare_only)

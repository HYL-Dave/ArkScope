"""Real Settings components, intercepted fixture API only; never start the App."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright, expect

HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
ROOT = HERE.parents[4]
CONTRACT = json.loads((ROOT / "tests/fixtures/price_repair_operations_v1.json").read_text())


def coverage(days, complete=False):
    gap = {"ticker": "FORMER", "reason": "before_first_local_bar", "first_local_bar_at": "2026-08-31T13:30:00Z",
           "missing_dates": ["2026-08-28"], "partial_dates": [], "provider_issue_reason": None}
    return {"version": 2, "market_scope": "us_listed_equity_proxy", "coverage_session": "rth", "interval": "15min",
            "lookback_days": days, "universe_count": 183, "generated_at_et": "2026-09-05T17:00:00-04:00",
            "calendar_health": {"status": "ok", "reason_codes": [], "reviewed_through": "2027-12-31", "forward_horizon_months": 15},
            "observation_health": {"status": "ok", "reason_code": None}, "provider_errors": [], "history_gaps": [] if complete else [gap],
            "days": [{"date": "2026-09-04", "coverage_status": "complete", "status_reason_code": None, "closure_reason_code": None,
                      "session_kind": "regular", "session_open_at_utc": "2026-09-04T13:30:00Z", "session_close_at_utc": "2026-09-04T20:00:00Z",
                      "expected_slot_count": 26, "observed_ticker_count": 183, "complete_ticker_count": 183, "partial_ticker_count": 0,
                      "unknown_ticker_count": 0, "partial_tickers": [], "unknown_tickers": [], "unmatched_rth_row_count": 0}]}


def install_routes(page, url, scenario):
    state = {"posts": [], "unexpected": [], "coverage_windows": [], "complete": False}
    records = [deepcopy(CONTRACT[key]) for key in ("cached", "unanswered", "scope_changed", "journal_unavailable", "complete")]
    for index, record in enumerate(records):
        record["repair_id"] = format(index + 1, "x") * 32
    def handle(route):
        parsed = urlparse(route.request.url)
        if parsed.netloc == urlparse(url).netloc:
            route.continue_()
            return
        code = 200
        path = parsed.path
        if parsed.hostname not in {"127.0.0.1", "localhost"}:
            state["unexpected"].append(path)
            route.abort()
            return
        if route.request.method == "POST":
            state["posts"].append(path)
            if path == "/market-data/price-repair/" + "1" * 32 + "/resume":
                if scenario == "response_lost":
                    value, code = {"detail": {"code": "price_repair_resume_unavailable"}}, 503
                else:
                    state["complete"] = True
                    records[0] = {**deepcopy(CONTRACT["complete"]), "repair_id": "1" * 32}
                    value = {"status": "accepted", "repair_id": "1" * 32}
            else:
                state["unexpected"].append(path)
                value, code = {"detail": {"code": "unexpected_fixture_write"}}, 409
        elif path == "/market-data/status":
            value = {"exists": False, "market_db": "fixture", "prices": {}, "news": {}, "fundamentals": {}, "financial_cache": {}, "sync": {},
                     "prices_authority": "local", "fundamentals_mode": "local_cache_refetch", "routing_enabled": True, "strict_enabled": True}
        elif path == "/market-data/trading-days":
            days = int(parse_qs(parsed.query)["lookback_days"][0])
            state["coverage_windows"].append(days)
            value = coverage(days, state["complete"])
        elif path == "/market-data/price-repair/operations":
            value = {"version": 1, "operations": None if scenario == "malformed" else records, "total": 5, "offset": 0, "has_more": False}
        elif path == "/market-data/price-repair/" + "1" * 32:
            value = records[0]
        elif path == "/schedule":
            result = {"status": "succeeded", "price_repair_id": "1" * 32} if state["complete"] else None
            value = {"sources": {"ibkr_prices": {"running": False, "last_result": result}}}
        elif path == "/security-lifecycle/cases":
            value = {"cases": [], "count": 0, "queue_counts": {"attention": 0, "monitoring": 0, "history": 0},
                     "admission_counts": {"admitted": 0, "needs_review": 0, "pending": 0, "screened_out": 0}, "data_integrity": {"source_missing_count": 0}}
        elif path == "/security-lifecycle/automation":
            value = {"config_status": "valid", "config": {"enabled": False, "interval_minutes": 5, "batch_limit": 2, "apply_profile_transitions": False},
                     "schedule": {"status": "disabled", "last_attempt_at": None, "next_scheduled_at": None}, "telemetry_status": "absent",
                     "last_status": None, "last_result": None, "active_incident": None, "latest_failed_runs": [], "current_progress": []}
        else:
            state["unexpected"].append(path)
            value, code = {"detail": {"code": "unexpected_fixture_read"}}, 404
        route.fulfill(status=code, content_type="application/json", body=json.dumps(value), headers={"Access-Control-Allow-Origin": "*"})
    page.route("**/*", handle)
    return state


def geometry(page, selector):
    return page.locator(selector).evaluate("""root => {
      const visible = node => node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden';
      const controls = [...root.querySelectorAll('button,input,select')].filter(visible).map(node => {
        const r = node.getBoundingClientRect(); return {text: node.textContent || node.getAttribute('aria-label'), left:r.left, right:r.right, top:r.top, bottom:r.bottom};
      });
      const overlaps = controls.flatMap((a,i) => controls.slice(i+1).filter(b => Math.min(a.right,b.right)-Math.max(a.left,b.left)>1 && Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1).map(b => [a.text,b.text]));
      const clipped = controls.filter(a => a.left < -1 || a.right > innerWidth+1);
      const overflow = [...root.querySelectorAll('p,button,strong')].filter(visible).filter(node => node.scrollWidth > node.clientWidth+2 && getComputedStyle(node).display !== 'inline').map(node => node.textContent);
      return {overlaps, clipped, overflow, bodyOverflow: document.documentElement.scrollWidth > innerWidth+1};
    }""")


def main():
    output = PACKET / "browser"
    output.mkdir(exist_ok=True)
    server = subprocess.Popen(["node", str(HERE / "serve_preview.mjs")], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    results = []
    try:
        line = server.stdout.readline()
        if not line:
            raise RuntimeError(server.stderr.read())
        url = json.loads(line)["url"]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for locale in ("en", "zh-Hant"):
                for width, height in ((1440, 900), (390, 844), (320, 740)):
                    for scenario in ("success", "response_lost", "malformed"):
                        context = browser.new_context(viewport={"width": width, "height": height}, service_workers="block")
                        page = context.new_page()
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        state = install_routes(page, url, scenario)
                        page.goto(url + "?locale=" + locale)
                        section = '[data-settings-location="trading_day_coverage"]'
                        page.locator(section).scroll_into_view_if_needed()
                        expect(page.locator(section).get_by_role("combobox")).to_have_value("15")
                        label = "Saved backfills" if locale == "en" else "補抓紀錄"
                        history = page.get_by_role("region", name=label)
                        if scenario == "malformed":
                            expect(history.get_by_role("alert")).to_be_visible()
                        else:
                            resume = history.get_by_role("button", name="Resume backfill" if locale == "en" else "繼續補抓", exact=True)
                            expect(resume).to_be_enabled()
                        assert state["posts"] == [] and state["coverage_windows"][0] == 15
                        metrics = geometry(page, section)
                        assert not any(metrics.values()), metrics
                        name = f"{locale}-{width}-{scenario}"
                        page.screenshot(path=str(output / (name + ".png")), full_page=True)
                        assert max(ImageStat.Stat(Image.open(output / (name + ".png"))).var) > 5
                        if scenario != "malformed":
                            resume.click()
                            dialog = page.get_by_role("dialog")
                            expect(dialog).to_contain_text("No new provider requests" if locale == "en" else "不新增 provider 請求")
                            assert state["posts"] == []
                            modal_metrics = geometry(page, '[role="dialog"]')
                            assert not any(modal_metrics.values()), modal_metrics
                            page.screenshot(path=str(output / (name + "-confirm.png")))
                            dialog.get_by_role("button", name="Confirm resume" if locale == "en" else "確認續作", exact=True).click()
                            expect(dialog).not_to_be_visible()
                            if scenario == "success":
                                expect(history.get_by_text("Coverage complete" if locale == "en" else "價格覆蓋完整", exact=True)).to_have_count(2)
                                page.reload()
                                expect(page.get_by_role("region", name=label).get_by_text("Coverage complete" if locale == "en" else "價格覆蓋完整", exact=True)).to_have_count(2)
                            else:
                                expect(history.get_by_role("alert")).to_be_visible()
                            assert len(state["posts"]) == 1
                        assert not state["unexpected"], state["unexpected"]
                        assert not errors, errors
                        results.append({"name": name, "geometry": metrics, "mocked_posts": len(state["posts"]), "unexpected_requests": state["unexpected"], "page_errors": errors})
                        context.close()
            browser.close()
        (output / "results.json").write_text(json.dumps({"scenarios": results, "provider_calls": 0, "production_app_started": False}, indent=2) + "\n")
        print(json.dumps({"scenarios": len(results), "provider_calls": 0}), flush=True)
    finally:
        server.terminate()
        try:
            server.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.communicate()


if __name__ == "__main__":
    main()

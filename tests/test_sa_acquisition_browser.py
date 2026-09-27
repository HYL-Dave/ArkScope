"""Installed Firefox/Chromium with fake pages, real durable native authority.

Opt in with ARKSCOPE_BROWSER_ACCEPTANCE=1. These tests need local browser binaries,
Playwright and Selenium; they never connect to SA or a registered native host.
"""
from contextlib import ExitStack
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time

import pytest

from tests.test_sa_extension_packaging import EXT_DIR, _load_builder


@pytest.mark.skipif(os.environ.get("ARKSCOPE_BROWSER_ACCEPTANCE") != "1", reason="installed browser acceptance is an explicit isolated gate")
def test_installed_browsers_share_durable_acquisition(tmp_path, monkeypatch):
    from playwright.sync_api import sync_playwright
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service
    from selenium.webdriver.support.ui import Select
    from src.sa.company_collector import CompanyCollector
    from src.sa.company_store import save_capture
    from tests.test_sa_company_data import capture

    monkeypatch.setenv("ARKSCOPE_SA_DB", str(tmp_path / "sa.db"))
    collector = CompanyCollector(tmp_path / "control.db")
    saved, admissions = [], []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b"Offline provider fixture")

        def do_POST(self):
            message = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if message["operation"] == "fixture_save":
                payload = capture(ticker=message["ticker"])
                payload["captured_at"] = datetime.now(timezone.utc).isoformat()
                result = save_capture(payload)
                saved.append((message["ticker"], time.time()))
            else:
                result = collector.handle(message)
                if message["operation"] == "admit_navigation" and result.get("allowed"):
                    admissions.append((message["client"]["browser"], message["destination_class"], time.time()))
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps(result).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        with ExitStack() as stack:
            packages = {}
            for browser in ("firefox", "chrome"):
                folder = tmp_path / browser
                if browser == "firefox": _load_builder().build_firefox(EXT_DIR, folder)
                else: shutil.copytree(EXT_DIR, folder, ignore=shutil.ignore_patterns("__pycache__"))
                manifest = json.loads((folder / "manifest.json").read_text())
                manifest["host_permissions"] = ["http://127.0.0.1/*"]
                manifest["name"] = "ArkScope Offline Acquisition Test"
                if browser == "firefox":
                    manifest["browser_specific_settings"]["gecko"]["id"] = "offline-acquisition@arkscope.local"
                    scripts = manifest["background"]["scripts"]
                    manifest["background"]["scripts"] = [scripts[0], "fixture_pre.js", *scripts[1:], "fixture_hooks.js"]
                else:
                    manifest["background"]["service_worker"] = "fixture_worker.js"
                    (folder / "fixture_worker.js").write_text("importScripts('fixture_pre.js','background.js','fixture_hooks.js');")
                (folder / "manifest.json").write_text(json.dumps(manifest))
                client = {"browser": browser, "client_id": ("f" if browser == "firefox" else "c") * 32}
                pre = f"var ARK_FIXTURE_URL={json.dumps(url)},ARK_FIXTURE_CLIENT={json.dumps(client)};\n"
                pre += """
                const realCreate=chrome.tabs.create.bind(chrome.tabs);
                chrome.tabs.create=opts=>realCreate({...opts,url:ARK_FIXTURE_URL+'/page'});
                chrome.runtime.sendNativeMessage=(_host,_msg,cb)=>{if(cb)cb({status:'error',error_code:'offline_fixture_native_disabled'});return Promise.resolve({status:'error'});};
                // Authority-only fixture; real port lifetime has a separate
                // ping-only host test. Never open a registered production host.
                chrome.runtime.connectNative=()=>{
                  const listeners=new Set();
                  return {onMessage:{addListener:fn=>listeners.add(fn),removeListener:fn=>listeners.delete(fn)},
                    onDisconnect:{addListener(){},removeListener(){}},
                    postMessage(){Promise.resolve().then(()=>listeners.forEach(fn=>fn({status:'ok'})));},disconnect(){}};
                };
                """
                (folder / "fixture_pre.js").write_text(pre)
                shutil.copyfile(Path(__file__).parent / "js/run_sa_acquisition_browser_fixture.mjs", folder / "fixture_hooks.js")
                packages[browser] = folder

            profiles = stack.enter_context(tempfile.TemporaryDirectory(prefix="arkscope-offline-acquisition-", dir=Path.home() / "snap/firefox/common"))
            options = Options(); options.binary_location = "/snap/firefox/current/usr/lib/firefox/firefox"
            options.add_argument("-headless"); options.set_preference("network.proxy.type", 1)
            for scheme in ("http", "ssl"):
                options.set_preference("network.proxy." + scheme, "127.0.0.1")
                options.set_preference("network.proxy." + scheme + "_port", 9)
            options.set_preference("network.proxy.no_proxies_on", "127.0.0.1,localhost")
            driver = webdriver.Firefox(options=options, service=Service(executable_path="/snap/bin/geckodriver",
                service_args=["--profile-root", profiles, "--allow-system-access"], log_output=str(tmp_path / "gecko.log")))
            stack.callback(driver.quit)
            addon_id = driver.install_addon(str(packages["firefox"]), temporary=True)
            driver.set_context("chrome")
            identity = driver.execute_script('return JSON.parse(Services.prefs.getStringPref("extensions.webextensions.uuids"))[arguments[0]]', addon_id)
            driver.set_context("content"); driver.set_script_timeout(30)
            firefox_popup = f"moz-extension://{identity}/popup.html"
            keeper = driver.current_window_handle
            driver.switch_to.new_window("tab")
            driver.get(firefox_popup)
            driver.set_context("chrome")
            errors = driver.execute_script('return Services.console.getMessageArray().map(x=>x.message).filter(x=>x.includes(arguments[0]) && x.includes("JavaScript Error"))', identity)
            driver.set_context("content")
            assert not errors, errors

            def ff(command, **extra):
                result = driver.execute_async_script("const done=arguments[arguments.length-1];browser.runtime.sendMessage(arguments[0]).then(done,e=>done({fixture_error:String(e)}));",
                    dict(action="offline_fixture", command=command, **extra))
                if not result or "fixture_error" in result:
                    driver.set_context("chrome")
                    print(driver.execute_script('return Services.console.getMessageArray().map(x=>x.message).filter(x=>x.includes(arguments[0]) || x.includes("127.0.0.1"))', identity))
                    driver.set_context("content")
                assert result and "fixture_error" not in result, (command, result)
                return result

            pw = stack.enter_context(sync_playwright())
            chromium_profile = tmp_path / "chromium-profile"
            (chromium_profile / "Default").mkdir(parents=True)
            # Unpacked reloads require developer mode, even when the initial CLI load succeeds.
            (chromium_profile / "Default/Preferences").write_text(json.dumps({"extensions": {"ui": {"developer_mode": True}}}))
            chromium = pw.chromium.launch_persistent_context(str(chromium_profile), headless=True, channel="chromium",
                args=[f"--disable-extensions-except={packages['chrome']}", f"--load-extension={packages['chrome']}",
                    "--proxy-server=http://127.0.0.1:9", "--proxy-bypass-list=127.0.0.1;localhost"])
            stack.callback(chromium.close)
            worker = chromium.service_workers[0] if chromium.service_workers else chromium.wait_for_event("serviceworker")
            page = chromium.new_page(); page.goto(worker.url.rsplit("/", 1)[0] + "/popup.html")

            def ch(command, **extra):
                return page.evaluate("message=>chrome.runtime.sendMessage(message)", dict(action="offline_fixture", command=command, **extra))

            def wait_for(predicate, label, seconds=50):
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    state = ff("snapshot")
                    if predicate(state): return state
                    time.sleep(.2)
                raise AssertionError({"timeout": label, "state": state, "saved": saved, "admissions": admissions})

            def ff_click(selector):
                element = driver.find_element("css selector", selector)
                driver.execute_script("arguments[0].scrollIntoView({block:'center'})", element)
                element.click()

            def ff_activate(enabled=False):
                driver.get(firefox_popup)
                wait_for(lambda _: driver.find_element("id", "companyCollectorStatus").text.startswith("Collector:"), "Firefox popup ready")
                Select(driver.find_element("id", "companyRefreshTargetMode")).select_by_value("watchlist")
                if driver.find_element("id", "companyRefreshEnabled").is_selected() != enabled:
                    ff_click("#companyRefreshEnabled")
                if not driver.find_element("id", "companyAdvanced").get_attribute("open"):
                    ff_click("#companyAdvanced summary")
                assert not driver.find_element("id", "companyBudgetEnabled").is_selected()
                for selector, value in {"#companyFinancialGap": 15}.items():
                    element = driver.find_element("css selector", selector)
                    element.clear(); element.send_keys(str(value))
                ff_click("#companyActivationConfirmed")
                ff_click("#companyCollectorSelect")
                wait_for(lambda s: s["collector"].get("is_owner") and s["refresh"]["config"]["enabled"] is enabled
                         and driver.find_element("id", "companyCollectorSelect").is_enabled(), "Firefox activation complete")

            assert not saved and not admissions
            ff_activate()
            assert ff("snapshot")["collector"]["policy"] == {
                "hour_limit": None, "day_limit": None, "hour_reserve": 0, "day_reserve": 0}
            driver.save_screenshot(str(tmp_path / "firefox-unified.png"))
            assert driver.execute_script("return document.body.scrollWidth <= innerWidth")
            assert ch("news")["reason"] == "collector_other_installation"
            ff_click("#companyRefreshNow")
            first = wait_for(lambda s: len(saved) == 1 and not s["refresh"]["running"], "first scope")
            assert first["collector"]["active"] is None
            routine = ff("news")
            assert routine.get("detail_fetched") == 1, routine
            both = wait_for(lambda s: len(saved) == 2 and not s["refresh"]["running"], "15 second active continuation")
            assert [item[0] for item in saved] == ["AAPL", "AMD"]
            assert saved[1][1] - saved[0][1] >= 15
            assert [item[1] for item in admissions[:3]] == ["financials", "news", "financials"]
            assert both["collector"]["active"] is None and not both["stored"]["saAcquisitionPending"]

            for during_update in (False, True):
                interrupted = ff("closed_picks", duringUpdate=during_update)
                assert interrupted["acquisition_stop"]["error_code"] == "interrupted", interrupted
                assert "acquisition" in interrupted and not interrupted.get("acquisition_uncertain")
                stopped = ff("snapshot")
                assert stopped["collector"]["active"] is None and not stopped["stored"]["saAcquisitionPending"]

            ff("run"); time.sleep(.4)
            assert len(saved) == 2
            ff("alarm"); time.sleep(1)
            assert len(saved) == 2
            ff_activate(enabled=True)
            if not driver.find_element("id", "companyAdvanced").get_attribute("open"):
                ff_click("#companyAdvanced summary")
            ff_click("#companyForceConfirmed")
            ff_click("#companyRefreshForce")
            wait_for(lambda s: s["refresh"]["pending_count"] > 0, "force queued from Firefox popup")
            assert ff("snapshot")["refresh"]["config"]["enabled"] is True
            ff("cancel")
            assert ff("snapshot")["refresh"]["pending_count"] == 0

            # A real extension reload destroys worker timers, retaining native pacing and browser storage.
            driver.execute_script("setTimeout(()=>browser.runtime.reload(),100)")
            driver.switch_to.window(keeper); time.sleep(2)
            driver.switch_to.new_window("tab")
            driver.get(firefox_popup)
            after = ff("snapshot")
            assert after["collector"]["next_financial_at"] == both["collector"]["next_financial_at"]
            assert len(saved) == 2

            lost = ff("lose_reply")
            assert lost.get("acquisition_uncertain") is True
            before = len(admissions)
            assert ff("news")["status"] == "deferred"
            assert len(admissions) == before
            assert ff("recover")["status"] == "ok"
            page.reload()
            page.wait_for_function("document.querySelector('#companyCollectorStatus').textContent.startsWith('Collector:')")
            page.locator("#companyRefreshTargetMode").select_option("watchlist")
            if not page.locator("#companyAdvanced").evaluate("element=>element.open"):
                page.locator("#companyAdvanced summary").click()
            page.locator("#companyFinancialGap").fill("15")
            page.locator("#companyBudgetEnabled").check()
            for key, value in {"hour_limit": 20, "day_limit": 100, "hour_reserve": 4, "day_reserve": 20}.items():
                page.locator('[name="'+key+'"]').fill(str(value))
            page.locator("#companyActivationConfirmed").check()
            page.locator("#companyCollectorSelect").click()
            wait_for(lambda _: ch("snapshot")["collector"].get("is_owner")
                     and page.locator("#companyCollectorSelect").is_enabled(), "Chromium popup activation")
            page.screenshot(path=str(tmp_path / "chromium-unified.png"), full_page=True)
            assert page.evaluate("document.body.scrollWidth <= innerWidth")
            assert ff("news")["reason"] == "collector_other_installation"
            assert ch("news").get("detail_fetched") == 1
            for during_update in (False, True):
                interrupted = ch("closed_picks", duringUpdate=during_update)
                assert interrupted["acquisition_stop"]["error_code"] == "interrupted", interrupted
                assert "acquisition" in interrupted and not interrupted.get("acquisition_uncertain")
                stopped = ch("snapshot")
                assert stopped["collector"]["active"] is None and not stopped["stored"]["saAcquisitionPending"]
            if not page.locator("#companyAdvanced").evaluate("element=>element.open"):
                page.locator("#companyAdvanced summary").click()
            page.locator("#companyForceConfirmed").check()
            page.locator("#companyRefreshForce").click()
            wait_for(lambda _: len(saved) == 4 and not ch("snapshot")["refresh"]["running"], "Chromium active continuation")
            assert saved[3][1] - saved[2][1] >= 15
            assert ch("snapshot")["refresh"]["config"]["enabled"] is False
            chrome_before = ch("snapshot")
            chrome_url = page.url
            page.evaluate("()=>{setTimeout(()=>chrome.runtime.reload(),100);}")
            time.sleep(2)
            page = chromium.new_page(); page.goto(chrome_url)
            assert ch("snapshot")["collector"]["next_financial_at"] == chrome_before["collector"]["next_financial_at"]
            assert len(saved) == 4
            current = ch("snapshot")
            count = current["collector"]["navigation_attempts"]
            assert ch("policy", policy={"hour_limit":count+1,"day_limit":100,"hour_reserve":0,"day_reserve":0})["status"] == "ok"
            partial = ch("news", count=3)
            assert partial["detail_fetched"] == 1 and partial["reason"] == "capacity_exhausted", partial
            assert ch("snapshot")["collector"]["active"] is None
            assert partial["extension_run"]["derived_outcome"] != "complete"
            assert ch("policy", policy={"hour_limit":40,"day_limit":100,"hour_reserve":4,"day_reserve":20})["status"] == "ok"
            page.reload()
            page.wait_for_function("document.querySelector('#companyBudgetEnabled').checked")
            page.locator("#companyAdvanced summary").click()
            page.locator("#companyBudgetEnabled").uncheck()
            page.locator("#companyActivationConfirmed").check()
            page.locator("#companyCollectorSelect").click()
            wait_for(lambda _: ch("snapshot")["collector"]["policy"]["hour_limit"] is None,
                     "Chromium disables page budget")
            before_count = ch("snapshot")["collector"]["navigation_attempts"]
            assert ch("news", count=3)["detail_fetched"] == 3
            assert ch("snapshot")["collector"]["navigation_attempts"] == before_count + 3
            assert ch("schedules")["status"] == "ok"
            ch("restrict", reason="login_required")
            paused = ch("snapshot")
            assert paused["collector"]["paused_reason"] == "login_required"
            assert paused["badge"] == "!"
            assert not any(a["name"] in {"alpha-picks-auto-sync", "market-news-auto-sync", "company-financial-refresh"} for a in paused["alarms"])
            before = len(admissions)
            assert ch("news")["reason"] == "site_paused"
            assert len(admissions) == before
            assert all("seekingalpha.com" not in t.get("url", "") for t in ch("snapshot")["tabs"])
            print(json.dumps({"browser": ["firefox", "chromium"], "ordered_admissions": admissions,
                "owner_generation": ch("snapshot")["collector"]["generation"], "stored_scopes": saved,
                "live_sa_requests": False, "native_transport": "local_test_rpc", "authority": "real_sqlite",
                "remaining_reservations": ch("snapshot")["collector"]["active"]}))
    finally:
        server.shutdown(); server.server_close(); thread.join()

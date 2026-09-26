"""Opt-in offline installed-browser regression for Alpha Picks document readiness.

Only native authority is stubbed. The production background, acquisition client,
access inspector, tab APIs and scripting permission checks run in fresh profiles.
Set ARKSCOPE_READINESS_EVIDENCE_DIR to retain JSON browser/server observations.

Response headers without HTML do not prove a browser has not committed an empty
document. That case records URL publication; it does not synthesize a commit race.
"""

from contextlib import ExitStack
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
from urllib.parse import parse_qs, urlsplit

import pytest

from tests.test_sa_extension_packaging import EXT_DIR, _load_builder


pytestmark = pytest.mark.skipif(
    os.environ.get("ARKSCOPE_BROWSER_ACCEPTANCE") != "1",
    reason="installed browser acceptance is an explicit isolated gate",
)
FIXTURES = Path(__file__).parent / "fixtures/sa_extension/alpha_readiness"
SCENARIOS = ("fresh_blank", "uncommitted", "response_started", "table_loading", "news_control")


@pytest.fixture(scope="module", params=["firefox", "chromium"])
def readiness_browser(request, tmp_path_factory):
    browser_name = request.param
    root = tmp_path_factory.mktemp("alpha-readiness-" + browser_name)
    evidence = Path(os.environ.get("ARKSCOPE_READINESS_EVIDENCE_DIR", str(root / "evidence")))
    evidence.mkdir(parents=True, exist_ok=True)
    states = {name: {"headers": threading.Event(), "document": threading.Event(), "body": threading.Event(),
                     "rendered": False, "page_visits": 0, "header_sent": False,
                     "document_sent": False, "body_released": False, "requests": []} for name in SCENARIOS}
    states["table_loading"]["headers"].set()
    states["response_started"]["headers"].set()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            target = urlsplit(self.path)
            name = parse_qs(target.query).get("case", [None])[0]
            state = states.get(name)
            if state is None:
                self.send_error(404)
                return
            state["requests"].append(target.path)
            if target.path == "/alpha-picks/picks/current":
                state["page_visits"] += 1
                if not state["headers"].wait(12):
                    self.send_error(504)
                    return
                data = (FIXTURES / "table.html").read_bytes()
                content_type = "text/html"
            elif target.path == "/hold":
                state["body"].wait(12)
                state["body_released"] = True
                data, content_type = b"offline load blocker", "image/png"
            else:
                if target.path == "/release_headers":
                    state["headers"].set()
                elif target.path == "/release_document":
                    state["document"].set()
                elif target.path == "/release_body":
                    state["body"].set()
                elif target.path == "/rendered":
                    state["rendered"] = True
                elif target.path != "/state":
                    self.send_error(404)
                    return
                data = json.dumps({key: value for key, value in state.items()
                                   if key not in ("headers", "document", "body")}).encode()
                content_type = "application/json"
            try:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if target.path == "/alpha-picks/picks/current":
                    state["header_sent"] = True
                    if name == "response_started":
                        self.wfile.flush()
                        state["document"].wait(12)
                    state["document_sent"] = True
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        with ExitStack() as stack:
            package = root / "extension"
            if browser_name == "firefox":
                _load_builder().build_firefox(EXT_DIR, package)
            else:
                shutil.copytree(EXT_DIR, package, ignore=shutil.ignore_patterns("__pycache__"))
            background_sha256 = hashlib.sha256((package / "background.js").read_bytes()).hexdigest()
            shutil.copyfile(package / "background.js", evidence / f"background-{background_sha256}.js")
            manifest = json.loads((package / "manifest.json").read_text())
            manifest["name"] = "ArkScope Offline Alpha Readiness Test"
            manifest["host_permissions"] = ["http://127.0.0.1/*"]
            # No native permission remains, so accidental fixture escape cannot
            # open a registered host even though only sendNativeMessage is stubbed.
            manifest["permissions"] = [permission for permission in manifest["permissions"] if permission != "nativeMessaging"]
            for name in ("native.js", "hooks.js", "driver.html"):
                shutil.copyfile(FIXTURES / name, package / ("readiness_" + name))
            if browser_name == "firefox":
                manifest["browser_specific_settings"]["gecko"]["id"] = "offline-alpha-readiness@arkscope.local"
                scripts = manifest["background"]["scripts"]
                manifest["background"]["scripts"] = [scripts[0], "readiness_native.js", *scripts[1:], "readiness_hooks.js"]
            else:
                manifest["background"]["service_worker"] = "readiness_worker.js"
                (package / "readiness_worker.js").write_text(
                    "importScripts('readiness_native.js','background.js','readiness_hooks.js');\n")
            (package / "manifest.json").write_text(json.dumps(manifest))

            if browser_name == "firefox":
                from selenium import webdriver
                from selenium.webdriver.firefox.options import Options
                from selenium.webdriver.firefox.service import Service

                profiles = stack.enter_context(tempfile.TemporaryDirectory(
                    prefix="arkscope-alpha-readiness-", dir=Path.home() / "snap/firefox/common"))
                options = Options()
                options.binary_location = "/snap/firefox/current/usr/lib/firefox/firefox"
                options.add_argument("-headless")
                options.set_preference("network.proxy.type", 1)
                for scheme in ("http", "ssl", "socks"):
                    options.set_preference("network.proxy." + scheme, "127.0.0.1")
                    options.set_preference("network.proxy." + scheme + "_port", 9)
                options.set_preference("network.proxy.no_proxies_on", "127.0.0.1,localhost")
                options.set_preference("network.trr.mode", 5)
                options.set_preference("network.proxy.failover_direct", False)
                options.set_preference("network.dns.disablePrefetch", True)
                options.set_preference("network.prefetch-next", False)
                options.set_preference("media.peerconnection.enabled", False)
                driver = webdriver.Firefox(options=options, service=Service(
                    executable_path="/snap/bin/geckodriver",
                    service_args=["--profile-root", profiles, "--allow-system-access"],
                    log_output=str(evidence / "firefox-gecko.log")))
                stack.callback(driver.quit)
                addon = driver.install_addon(str(package), temporary=True)
                driver.set_context("chrome")
                identity = driver.execute_script(
                    'return JSON.parse(Services.prefs.getStringPref("extensions.webextensions.uuids"))[arguments[0]]', addon)
                driver.set_context("content")
                driver.set_script_timeout(25)
                driver.set_page_load_timeout(20)
                driver.get(f"moz-extension://{identity}/readiness_driver.html")

                def send(message):
                    return driver.execute_async_script(
                        "const done=arguments[arguments.length-1];"
                        "browser.runtime.sendMessage(arguments[0]).then(done,e=>done({fixtureError:String(e)}));", message)
            else:
                from playwright.sync_api import sync_playwright

                pw = stack.enter_context(sync_playwright())
                context = pw.chromium.launch_persistent_context(
                    str(root / "chrome-profile"), headless=True, channel="chromium", timeout=20000,
                    args=[f"--disable-extensions-except={package}", f"--load-extension={package}",
                          "--proxy-server=http://127.0.0.1:9", "--proxy-bypass-list=127.0.0.1;localhost",
                          "--disable-background-networking", "--disable-quic",
                          "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1"])
                stack.callback(context.close)
                context.set_default_timeout(25000)
                worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
                page = context.new_page()
                page.goto(worker.url.rsplit("/", 1)[0] + "/readiness_driver.html")

                def send(message):
                    return page.evaluate("message => Promise.race([chrome.runtime.sendMessage(message),"
                                         "new Promise(resolve=>setTimeout(()=>resolve({fixtureError:'driver timeout'}),25000))])", message)

            def run(scenario):
                report = send({"action": "offline_alpha_readiness", "origin": origin, "scenario": scenario})
                report["background_sha256"] = background_sha256
                report["browser_name"] = browser_name
                (evidence / f"{browser_name}-{scenario}.json").write_text(json.dumps(report, indent=2) + "\n")
                print(json.dumps({key: report.get(key) for key in (
                    "browser_name", "scenario", "helper", "initial", "outcome", "elapsedMs",
                    "atOutcome", "background_sha256", "fixtureError")}, sort_keys=True))
                return report

            yield run
    finally:
        for state in states.values():
            state["headers"].set()
            state["document"].set()
            state["body"].set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_alpha_readiness_real_browser_permissions(readiness_browser, scenario):
    report = readiness_browser(scenario)
    assert "fixtureError" not in report, report
    assert report["helper"] == ("waitForTabLoad" if scenario == "news_control" else "waitForAlphaPicksTableReady")
    assert report["accessInspector"] == "inspectSaAccess"
    assert report["apisUntouched"] is True
    assert report["hostPermissions"] == ["http://127.0.0.1/*"]
    assert report["grantedPermissions"]["origins"] == ["http://127.0.0.1/*"]
    assert "nativeMessaging" not in report["grantedPermissions"]["permissions"]
    assert report["serverFinal"]["page_visits"] == 1, report
    assert report["table"]["status"] == "ready", report
    assert report["document"]["rows"] == 1
    assert [tab["id"] for tab in report["createdTabs"]] == [report["created"]["id"]], report
    assert sorted(tab["id"] for tab in report["remainingTabs"]) == sorted(report["originalTabIds"]), report
    calls = report["nativeCalls"]
    assert [call["kind"] for call in calls if call.get("operation") == "admit_navigation"] == (
        ["create", "update"] if scenario == "fresh_blank" else ["create"])
    assert any(call.get("operation") == "begin_task" for call in calls)
    assert any(call.get("operation") == "finish_task" for call in calls)
    if scenario == "fresh_blank":
        assert report["initial"]["url"] == "about:blank" or (
            report["initial"]["url"] == "" and report["initial"]["pendingUrl"] == "about:blank"), report
    if scenario == "uncommitted":
        assert report["serverBeforeWait"]["header_sent"] is False, report
        assert report["initial"]["status"] == "loading", report
        assert report["initial"]["url"] in ("", "about:blank") or report["expectedUrlAlreadyPublished"], report
    if scenario == "response_started":
        assert report["serverBeforeWait"]["header_sent"] is True, report
        assert report["serverBeforeWait"]["document_sent"] is False, report
        assert report["initial"]["status"] == "loading", report
    if scenario == "table_loading":
        assert report["initial"]["status"] == "loading", report
        assert report["serverBeforeWait"]["rendered"] is True, report
    assert report["outcome"] == {"kind": "resolved", "value": {"ok": True}}, report
    if scenario != "news_control":
        assert report["atOutcome"]["status"] == "loading", report
        assert report["serverAtOutcome"]["body_released"] is False, report
        assert report["document"]["readyState"] != "complete", report
    else:
        assert report["atOutcome"]["status"] == "complete", report

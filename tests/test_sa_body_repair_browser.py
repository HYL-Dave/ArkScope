"""A manual body batch must outlive its popup, without contacting SA."""

from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import shlex
import tempfile
import threading
import time
from uuid import uuid4

import pytest

from tests.test_sa_extension_packaging import EXT_DIR, _load_builder


@pytest.mark.skipif(os.environ.get("ARKSCOPE_BROWSER_ACCEPTANCE") != "1",
                    reason="installed browser acceptance is an explicit isolated gate")
@pytest.mark.parametrize("browser_name", ["firefox", "chromium"])
def test_body_batch_continues_with_popup_closed(tmp_path, browser_name):
    from src.sa.company_collector import CompanyCollector

    client = {"client_id": "f" * 32, "browser": "firefox" if browser_name == "firefox" else "chrome"}
    collector = CompanyCollector(tmp_path / "control.db")
    gap = 7 if browser_name == "firefox" else 35
    policy = {"hour_limit": 5, "day_limit": 5, "hour_reserve": 0, "day_reserve": 0}
    configured = collector.handle({"operation": "configure", "client": client,
        "policy": policy, "financial_gap_seconds": gap,
        "expected_generation": 0, "confirm_activation": True})
    selected = collector.handle({"operation": "select", "client": client,
        "expected_generation": configured["generation"], "confirm_schedules": True})
    assert selected["is_owner"]
    saved, admissions = [], []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Offline article fixture")

        def do_POST(self):
            message = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if message.get("operation") == "fixture_capture":
                saved.append((message["article_id"], time.time()))
                result = {"status": "ok", "body_saved": True}
            else:
                result = collector.handle({**message, "client": client})
                if message["operation"] == "admit_navigation" and result.get("allowed"):
                    admissions.append(time.time())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    unique = uuid4().hex
    host = "com.arkscope.offline_body_" + unique
    addon_id = "offline-body-" + unique + "@arkscope.local"
    try:
        with ExitStack() as stack:
            # Native registration is unique and removed on exit. This host only
            # answers ping; it cannot reach the App, a database or the internet.
            native_root = Path(stack.enter_context(tempfile.TemporaryDirectory(
                prefix="arkscope-body-native-", dir=Path.home() / "snap/firefox/common")))
            native_script = native_root / "host.py"
            native_script.write_text(r'''
import json, struct, sys
trace = open(__file__ + '.trace', 'a', buffering=1)
trace.write('started\n')
while True:
    header = sys.stdin.buffer.read(4)
    trace.write('header:' + str(len(header)) + '\n')
    if len(header) != 4:
        break
    size = struct.unpack("=I", header)[0]
    if size > 4096:
        break
    data = sys.stdin.buffer.read(size)
    if len(data) != size:
        break
    message = json.loads(data)
    trace.write('action:' + str(message.get('action')) + '\n')
    answer = {"status": "ok"} if message == {"action": "ping"} else {"status": "error"}
    encoded = json.dumps(answer).encode()
    sys.stdout.buffer.write(struct.pack("=I", len(encoded)) + encoded)
    sys.stdout.buffer.flush()
    trace.write('replied\n')
''')
            native_script.chmod(0o700)
            native_launcher = native_root / "launch.sh"
            # Snap cannot read the developer's hidden virtualenv. This fixture
            # uses only stdlib, so use the browser environment's system Python.
            native_launcher.write_text("#!/bin/sh\nexec /usr/bin/python3 -I -B "
                + shlex.quote(str(native_script)) + "\n")
            native_launcher.chmod(0o700)
            package = tmp_path / "extension"
            if browser_name == "firefox":
                _load_builder().build_firefox(EXT_DIR, package)
            else:
                shutil.copytree(EXT_DIR, package, ignore=shutil.ignore_patterns("__pycache__"))
            manifest = json.loads((package / "manifest.json").read_text())
            manifest["name"] = "ArkScope Offline Body Lifecycle Test"
            manifest["host_permissions"] = ["http://127.0.0.1/*"]
            if browser_name == "firefox":
                manifest["browser_specific_settings"]["gecko"]["id"] = addon_id
                scripts = manifest["background"]["scripts"]
                manifest["background"]["scripts"] = [scripts[0], "fixture_pre.js", *scripts[1:], "fixture_hooks.js"]
            else:
                manifest["background"]["service_worker"] = "fixture_worker.js"
                (package / "fixture_worker.js").write_text("importScripts('fixture_pre.js','background.js','fixture_hooks.js');")
            (package / "manifest.json").write_text(json.dumps(manifest))
            source = (package / "background.js").read_text()
            assert "com.mindfulrl.sa_alpha_picks" in source
            (package / "background.js").write_text(source.replace("com.mindfulrl.sa_alpha_picks", host))
            (package / "fixture_pre.js").write_text(
                "var ARK_BODY_FIXTURE_URL=" + json.dumps(url) + ";\n" + """
const realCreate = chrome.tabs.create.bind(chrome.tabs);
chrome.tabs.create = opts => realCreate({...opts,url:ARK_BODY_FIXTURE_URL+'/page'});
chrome.runtime.sendNativeMessage = (_host,message,callback) => {
  Promise.resolve().then(()=>fixtureNative(message)).then(callback);
};
""")
            (package / "fixture_hooks.js").write_text("""
async function fixtureRpc(message) {
  return (await fetch(ARK_BODY_FIXTURE_URL+'/rpc',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(message)})).json();
}
companyCollectorControl = (operation,extra) => fixtureRpc({...extra,operation});
async function fixtureNative(message) {
  if(message.action==='record_extension_job')return {status:'ok',persisted:true,run_id:1};
  if(message.action==='sa_acquisition_control')return companyCollectorControl(message.operation,message);
  if(message.action==='preview_article_body_recovery')return {
    status:'ok',manifest_id:'offline-body',as_of:'2026-09-25',counts:{targets:2},
    targets:[1000,1001].map(id=>({article_id:String(id),title:'Offline article '+id,
      url:'https://seekingalpha.com/alpha-picks/articles/'+id+'-fixture',body_sha256:'a'.repeat(64)}))};
  return {status:'error',error_code:'offline_fixture_disabled'};
}
sendNativeMessage2 = fixtureNative;
captureArticleBodyRecovery = async function(target,run) {
  if(run.cancelled)return {status:'cancelled'};
  let tab;
  try {
    tab=await managedSaTabs.create({url:target.url,active:true});
    return await fixtureRpc({operation:'fixture_capture',article_id:target.article_id});
  } finally {if(tab)await safeRemoveTab(tab.id);}
};
""")
            registry = {"name": host, "description": "Offline body lifecycle ping only",
                        "path": str(native_launcher), "type": "stdio"}

            if browser_name == "firefox":
                from selenium import webdriver
                from selenium.webdriver.firefox.options import Options
                from selenium.webdriver.firefox.service import Service

                registration = native_root / "native-messaging-hosts" / (host + ".json")
                registration.parent.mkdir()
                registration.write_text(json.dumps({**registry, "allowed_extensions": [addon_id]}))
                profiles = stack.enter_context(tempfile.TemporaryDirectory(
                    prefix="arkscope-body-firefox-", dir=Path.home() / "snap/firefox/common"))
                options = Options()
                options.binary_location = "/snap/firefox/current/usr/lib/firefox/firefox"
                options.add_argument("-headless")
                # Accelerate the real event-page lifetime only in this disposable
                # profile. No popup or polling message may keep it alive in the gap.
                options.set_preference("extensions.background.idle.timeout", 1500)
                options.set_preference("widget.use-xdg-desktop-portal.native-messaging", 0)
                options.set_preference("widget.use-xdg-desktop-portal.native-messaging-proxy", 0)
                options.set_preference("network.proxy.type", 1)
                for scheme in ("http", "ssl"):
                    options.set_preference("network.proxy." + scheme, "127.0.0.1")
                    options.set_preference("network.proxy." + scheme + "_port", 9)
                options.set_preference("network.proxy.no_proxies_on", "127.0.0.1,localhost")
                driver = webdriver.Firefox(options=options, service=Service(
                    executable_path="/snap/bin/geckodriver",
                    service_args=["--profile-root", profiles, "--allow-system-access"],
                    log_output=str(tmp_path / "gecko.log")))
                stack.callback(driver.quit)
                driver.set_context("chrome")
                # Redirect lookup only inside this disposable browser process;
                # never install a host or portal permission in the user's profile.
                native_directory = driver.execute_script("""
                  const file=Cc['@mozilla.org/file/local;1'].createInstance(Ci.nsIFile);
                  file.initWithPath(arguments[0]);
                  try {Services.dirsvc.undefine('XREUserNativeManifests');} catch (_) {}
                  Services.dirsvc.set('XREUserNativeManifests',file);
                  const {NativeManifests}=ChromeUtils.importESModule('resource://gre/modules/NativeManifests.sys.mjs');
                  NativeManifests._initializePromise=null;
                  NativeManifests._lookup=null;
                  return Services.dirsvc.get('XREUserNativeManifests',Ci.nsIFile).path;
                """, str(native_root))
                assert native_directory == str(native_root)
                driver.set_context("content")
                driver.install_addon(str(package), temporary=True)
                driver.set_context("chrome")
                identity = driver.execute_script(
                    'return JSON.parse(Services.prefs.getStringPref("extensions.webextensions.uuids"))[arguments[0]]', addon_id)
                driver.set_context("content")
                driver.set_script_timeout(20)
                popup = f"moz-extension://{identity}/popup.html"
                driver.get(popup)
                native_ready = driver.execute_async_script("""
                  const done=arguments[arguments.length-1],p=browser.runtime.connectNative(arguments[0]);
                  let answered=false;
                  const finish=value=>{if(!answered){answered=true;clearTimeout(timer);done(value);}};
                  const timer=setTimeout(()=>{finish({error:'fixture native timeout'});p.disconnect();},5000);
                  p.onMessage.addListener(reply=>{finish(reply);p.disconnect();});
                  p.onDisconnect.addListener(()=>finish({error:String(p.error)}));
                  p.postMessage({action:'ping'});
                """, host)
                driver.set_context("chrome")
                native_errors = driver.execute_script("return Services.console.getMessageArray().map(x=>x.message).filter(x=>/native|Native|offline_body/.test(x));")
                driver.set_context("content")
                trace_path = Path(str(native_script) + ".trace")
                if native_ready != {"status": "ok"}:
                    print(json.dumps(native_errors, indent=2))
                assert native_ready == {"status": "ok"}, {
                    "reply": native_ready, "trace": trace_path.read_text() if trace_path.exists() else "not launched",
                    "errors": native_errors,
                }

                def message(value):
                    return driver.execute_async_script(
                        "const done=arguments[arguments.length-1];browser.runtime.sendMessage(arguments[0]).then(done,e=>done({error:String(e)}));", value)

                def leave_popup():
                    driver.get("about:blank")

                def return_popup():
                    driver.get(popup)
            else:
                from playwright.sync_api import sync_playwright

                pw = stack.enter_context(sync_playwright())
                home = tmp_path / "chrome-home"
                home.mkdir()
                env = {**os.environ, "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config")}
                context = pw.chromium.launch_persistent_context(str(tmp_path / "chrome-profile"),
                    headless=True, channel="chromium", env=env,
                    args=[f"--disable-extensions-except={package}", f"--load-extension={package}",
                          "--proxy-server=http://127.0.0.1:9", "--proxy-bypass-list=127.0.0.1;localhost"])
                stack.callback(context.close)
                worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
                origin = worker.url.rsplit("/", 1)[0] + "/"
                directory = tmp_path / "chrome-profile" / "NativeMessagingHosts"
                directory.mkdir(parents=True, exist_ok=True)
                (directory / (host + ".json")).write_text(json.dumps({**registry, "allowed_origins": [origin]}))
                page = context.new_page()
                popup = origin + "popup.html"
                page.goto(popup)
                native_ready = page.evaluate("""host=>new Promise(done=>{
                  const p=chrome.runtime.connectNative(host);
                  let answered=false;
                  const finish=value=>{if(!answered){answered=true;clearTimeout(timer);done(value);}};
                  const timer=setTimeout(()=>{finish({error:'fixture native timeout'});p.disconnect();},5000);
                  p.onMessage.addListener(reply=>{finish(reply);p.disconnect();});
                  p.onDisconnect.addListener(()=>finish({error:chrome.runtime.lastError?.message||'disconnected'}));
                  p.postMessage({action:'ping'});
                })""", host)
                trace_path = Path(str(native_script) + ".trace")
                assert native_ready == {"status": "ok"}, {
                    "reply": native_ready, "trace": trace_path.read_text() if trace_path.exists() else "not launched",
                }

                def message(value):
                    return page.evaluate("message=>chrome.runtime.sendMessage(message)", value)

                def leave_popup():
                    page.goto("about:blank")

                def return_popup():
                    page.goto(popup)

            preview = message({"action": "preview_article_body_recovery"})
            assert preview["status"] == "ok", preview
            started = message({"action": "start_article_body_recovery", "manifest_id": preview["manifest_id"]})
            assert started["status"] == "ok", started
            leave_popup()
            deadline = time.monotonic() + gap + 15
            while len(saved) < 2 and time.monotonic() < deadline:
                # Poll only the local server, never the extension background.
                time.sleep(.2)
            return_popup()
            result = message({"action": "get_article_body_recovery_state"})
            assert len(saved) == 2, {"saved": saved, "result": result}
            assert saved[1][1] - saved[0][1] >= gap
            assert len(admissions) == 2
            assert result["batch"]["status"] == "complete", result
            assert result["batch"]["counts"]["saved"] == 2
            assert collector.handle({"operation": "status", "client": client})["active"] is None
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

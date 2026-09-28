"""Real Settings component with intercepted local API fixtures; no formal App."""

import json
from pathlib import Path
import socket
import subprocess
import time
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = {"max_articles_per_job": 0, "body_lookback_days": 0, "body_scope": "all_retained", "comment_scope": "current"}
HTML = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<main id="root" style="max-width:1080px;margin:24px auto;padding:16px;min-width:0"></main>
<script type="module">
import RefreshRuntime from '/@react-refresh';
RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;
window.__vite_plugin_react_preamble_installed__=true;
window.arkscope={apiBase:location.origin};
const {default:React}=await import('/node_modules/.vite/deps/react.js');
const {default:{createRoot}}=await import('/node_modules/.vite/deps/react-dom_client.js');
const {default:i18n}=await import('/node_modules/.vite/deps/i18next.js');
const {initializeI18n}=await import('/src/i18n/resources.ts');
const {installUiTokens}=await import('/src/ui/tokens.ts');
await import('/src/styles.css');await import('/src/ui/primitives.css');await import('/src/settings/settings.css');
initializeI18n(i18n,new URL(location.href).searchParams.get('locale'));installUiTokens(document.documentElement);
const {SAArticleAcquisitionSection}=await import('/src/settings/SAArticleAcquisitionSection.tsx');
createRoot(document.getElementById('root')).render(React.createElement(SAArticleAcquisitionSection));
</script></body></html>"""


@pytest.fixture(scope="module")
def settings_origin(tmp_path_factory):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    log = tmp_path_factory.mktemp("sa-settings-vite") / "vite.log"
    with log.open("w") as output:
        process = subprocess.Popen(["node", str(ROOT / "node_modules/vite/bin/vite.js"), "--host", "127.0.0.1",
                                    "--port", str(port), "--strictPort"], cwd=ROOT / "apps/arkscope-web", stdout=output, stderr=subprocess.STDOUT)
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(origin, timeout=1):
                        break
                except OSError:
                    assert process.poll() is None, log.read_text()
                    time.sleep(.1)
            else:
                pytest.fail(log.read_text())
            yield origin
        finally:
            process.terminate()
            process.wait(timeout=10)


@pytest.mark.parametrize("locale", ["en", "zh-Hant"])
@pytest.mark.parametrize("width", [1440, 940, 720, 390])
def test_article_settings_layout_and_save(settings_origin, locale, width, tmp_path):
    from playwright.sync_api import sync_playwright
    view = {"values": DEFAULTS.copy(), "defaults": DEFAULTS, "setting_source": "default", "error_code": None}
    calls, errors = [], []
    def route(request):
        url = request.request.url
        if not url.startswith(settings_origin):
            pytest.fail("unexpected network access: " + url)
        if "/__article_settings" in url:
            request.fulfill(status=200, content_type="text/html", body=HTML)
        elif url.endswith("/sa/article-acquisition-settings"):
            calls.append(request.request.method)
            if request.request.method == "PUT":
                view.update(values=request.request.post_data_json, setting_source="profile")
            request.fulfill(json=view)
        elif url.endswith("/sa/body-recovery-status"):
            request.fulfill(json={"status": "ok", "state": "waiting", "counts": {"selected": 128, "saved": 18, "skipped": 1, "failed": 0, "pending": 109},
                                 "reason_code": "sa_company_pacing", "next_eligible_at": "2026-09-29T02:00:00+00:00"})
        else:
            request.continue_()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": 1000})
        page.route("**/*", route)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(settings_origin + "/__article_settings?locale=" + locale)
        try:
            page.locator(".sa-article-fields input").first.wait_for(timeout=15000)
        except Exception:
            pytest.fail(json.dumps({"errors": errors, "body": page.locator("body").inner_text()}))
        assert calls == ["GET"]
        page.locator(".sa-article-fields input").first.fill("128")
        page.get_by_role("button", name="Save article settings" if locale == "en" else "儲存文章設定", exact=True).click()
        page.wait_for_function("document.querySelector('.sa-article-settings button:nth-child(2)').disabled")
        assert view["values"]["max_articles_per_job"] == 128
        assert page.locator("progress").evaluate("n=>n.max") == 128
        assert page.locator(".sa-article-fields").evaluate("root=>[...root.querySelectorAll('input,select')].every(n=>n.getBoundingClientRect().height>=32)")
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        assert page.locator(".sa-article-settings").evaluate("""root=>[...root.querySelectorAll('label,input,select,button')].every(n=>{
          const r=n.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&n.scrollWidth<=n.clientWidth+1;})""")
        page.screenshot(path=str(tmp_path / f"article-settings-{locale}-{width}.png"), full_page=True)
        assert errors == []
        browser.close()

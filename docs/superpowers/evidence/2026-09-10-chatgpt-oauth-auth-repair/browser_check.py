"""Real frontend/API decoding, synthetic HTTP responses, isolated Vite only."""
import errno
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[4]
OWN = Path(__file__).resolve().parent
OUT = ROOT / "tmp/chatgpt-oauth-auth-repair"
BASE = "http://127.0.0.1:8468"
HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Synthetic OAuth recovery check</title></head><body><div id="root"></div>
<script type="module">import RefreshRuntime from '/@react-refresh'; RefreshRuntime.injectIntoGlobalHook(window); window.$RefreshReg$=()=>{}; window.$RefreshSig$=()=>type=>type; window.__vite_plugin_react_preamble_installed__=true;</script>
<script type="module" src="/@fs/ENTRY"></script></body></html>""".replace("ENTRY", str(OWN / "preview.tsx"))
DETAIL = dict(code="reauth_required", task="card_synthesis", provider="openai",
              model="gpt-5.6-luna", effort="max", auth_mode="chatgpt_oauth")


def verify(browser, locale, width, height, diagnostics):
    context = browser.new_context(viewport=dict(width=width, height=height), service_workers="block")
    context.add_init_script("window.arkscope={apiBase:" + json.dumps(BASE + "/__mock") + "}")
    page = context.new_page()
    page.set_default_timeout(8000)
    errors, submitted = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def route(request):
        url = urlsplit(request.request.url)
        if url.netloc != "127.0.0.1:8468":
            errors.append("external request blocked")
            request.abort()
        elif url.path == "/__preview":
            request.fulfill(status=200, content_type="text/html", body=HTML)
        elif url.path == "/__mock/profile/investor":
            request.fulfill(json=dict(profile=dict(enabled=False)))
        elif url.path == "/__mock/analysis/cards":
            request.fulfill(json=dict(cards=[]))
        elif url.path == "/__mock/analysis/card/AMD":
            submitted.append(request.request.post_data_json)
            request.fulfill(status=502, json=dict(detail=DETAIL))
        elif url.path.startswith("/__mock/") or any(p in url.path for p in (".env", ".db", "/config/")):
            errors.append("unexpected request blocked: " + url.path)
            request.abort()
        else:
            request.continue_()

    page.route("**/*", route)
    page.goto(f"{BASE}/__preview?locale={locale}&diagnostics={int(diagnostics)}")
    page.locator(".aicard-q").fill("Synthetic question retained after failure.")
    page.get_by_role("button", name="Generate Card" if locale == "en" else "產生卡片").click()
    alert = page.get_by_role("alert")
    expect(alert).to_contain_text("sign-in is no longer valid" if locale == "en" else "登入已失效")
    expect(alert.get_by_role("button")).to_have_count(1)
    expect(page.locator(".aicard-q")).to_have_value("Synthetic question retained after failure.")
    expect(alert).not_to_contain_text("synthetic-token")
    geometry = alert.evaluate("""el => {
      const a=el.getBoundingClientRect(), b=el.querySelector('button').getBoundingClientRect(),
        d=el.querySelector('.ui-inline-alert-detail').getBoundingClientRect();
      return {pageFits:document.documentElement.scrollWidth<=innerWidth,
        guidanceReadable:d.width>=200,
        actionFits:b.x>=a.x && b.right<=a.right+1 && b.y>=a.y && b.bottom<=a.bottom+1};
    }""")
    assert all(geometry.values()), geometry
    path = OUT / f"{locale}-{width}-diagnostics-{int(diagnostics)}.png"
    page.screenshot(path=str(path), full_page=True)
    alert.get_by_role("button").click()
    assert page.locator("body").get_attribute("data-navigation") == json.dumps(
        dict(kind="settings_section", section="providers"), separators=(",", ":"))
    assert len(submitted) == 1 and errors == [], (submitted, errors)
    assert "provider" not in submitted[0] and "model" not in submitted[0]
    context.close()
    return dict(locale=locale, width=width, diagnostics=diagnostics, requests=1,
                geometry=geometry, errors=errors, screenshot=str(path.relative_to(ROOT)))


def main():
    if "--worker" not in sys.argv:
        env = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "LANG", "LC_ALL"}}
        return subprocess.run([shutil.which("unshare"), "--user", "--map-root-user", "--net",
                               sys.executable, str(Path(__file__).resolve()), "--worker"], env=env).returncode
    subprocess.run([shutil.which("ip"), "link", "set", "lo", "up"], check=True)
    with socket.socket() as probe:
        assert probe.connect_ex(("192.0.2.1", 443)) == errno.ENETUNREACH
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "vite.log").open("w") as log:
        server = subprocess.Popen([shutil.which("node"), str(ROOT / "node_modules/vite/bin/vite.js"),
                                   "--host", "127.0.0.1", "--port", "8468"],
                                  cwd=ROOT / "apps/arkscope-web", stdout=log, stderr=log)
        try:
            for _ in range(80):
                with socket.socket() as sock:
                    if sock.connect_ex(("127.0.0.1", 8468)) == 0:
                        break
                assert server.poll() is None, "Vite startup failed"
                time.sleep(0.1)
            with sync_playwright() as p:
                browser = p.chromium.launch()
                results = [verify(browser, locale, w, h, diagnostics)
                           for locale in ("zh-Hant", "en") for w, h in ((1280, 900), (390, 844))
                           for diagnostics in (False, True)]
                browser.close()
            result = dict(external_network="ENETUNREACH", synthetic_only=True, results=results)
            (OUT / "browser-results.json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result))
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

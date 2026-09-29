"""A Settings hot update must not replace a shared context under live consumers."""

from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def isolated_settings_vite(tmp_path):
    # Source edits and Vite's dependency cache must never touch the running App.
    with tempfile.TemporaryDirectory(prefix="settings-hmr-", dir=tmp_path) as directory:
        project = Path(directory)
        web = ROOT / "apps/arkscope-web"
        shutil.copytree(web / "src", project / "src")
        for name in ("index.html", "package.json", "tsconfig.json", "vite.config.ts"):
            shutil.copy2(web / name, project / name)
        (project / "node_modules").symlink_to(ROOT / "node_modules", target_is_directory=True)
        (project / "hmr.config.ts").write_text(
            'import config from "./vite.config";\n'
            'export default {...config, cacheDir: "./.vite"};\n'
        )
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        with (tmp_path / "vite.log").open("w") as output:
            process = subprocess.Popen(
                ["node", str(ROOT / "node_modules/vite/bin/vite.js"),
                 "--config", "hmr.config.ts", "--host", "127.0.0.1",
                 "--port", str(port), "--strictPort"],
                cwd=project, stdout=output, stderr=subprocess.STDOUT,
            )
            try:
                for _ in range(100):
                    try:
                        with urllib.request.urlopen(origin, timeout=1):
                            break
                    except OSError:
                        assert process.poll() is None, (tmp_path / "vite.log").read_text()
                        time.sleep(0.1)
                else:
                    pytest.fail((tmp_path / "vite.log").read_text())
                yield project, origin
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


@pytest.mark.parametrize("source_name,burst", [
    ("secFilingForms.ts", False),
    ("dataScheduleControls.tsx", False),
    ("dataScheduleControls.tsx", True),
])
def test_data_settings_survive_hot_update(isolated_settings_vite, source_name, burst):
    from playwright.sync_api import expect, sync_playwright

    project, origin = isolated_settings_vite
    errors, unexpected_requests, mutations = [], [], []
    if source_name == "dataScheduleControls.tsx":
        # HMR importers can finish at different times. Exercise that ordering
        # without delaying the real App or reaching a real API.
        settings = project / "src/Settings.tsx"
        settings.write_text(settings.read_text() + "\nawait new Promise(resolve => setTimeout(resolve, 200));\n")

    def route(request):
        url = request.request.url
        if url.startswith(origin + "/__offline_api/"):
            if request.request.method != "GET":
                mutations.append(request.request.method)
            request.fulfill(status=503, json={"detail": "Offline HMR regression"})
        elif url.startswith(origin + "/"):
            request.continue_()
        else:
            unexpected_requests.append(url)
            request.abort()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.route("**/*", route)
            page.add_init_script("""
                window.arkscope = {apiBase: location.origin + '/__offline_api'};
                localStorage.setItem('arkscope.ui.locale.v1', 'en');
                localStorage.setItem('arkscope.settings.activeGroup.v1', 'data_sync');
                localStorage.setItem('arkscope.shell.developerMode.v1', 'enabled');
            """)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(origin, wait_until="networkidle")
            page.get_by_role("button", name="Settings", exact=True).click()
            sources = page.locator('[data-settings-anchor="data_sources"]')
            expect(sources).to_be_visible()
            expect(page.locator('[data-settings-anchor="macro_storage"]')).to_be_attached()
            assert errors == []
            page.evaluate("""async () => {
                window.__hmrRevision = -1;
                window.__hmrEvaluatedRevision = -1;
                window.__hmrCompletedRevision = -1;
                window.__hmrPendingBatches = 0;
                window.__hmrLastActivity = Date.now();
                const {createHotContext} = await import('/@vite/client');
                const hot = createHotContext('/__hmr_regression_listener');
                hot.on('vite:beforeUpdate', () => {
                    window.__hmrPendingBatches++;
                    window.__hmrLastActivity = Date.now();
                });
                hot.on('vite:afterUpdate', () => {
                    window.__hmrPendingBatches--;
                    window.__hmrLastActivity = Date.now();
                });
                window.__registerBeforePerformReactRefresh(() => {
                    const revision = window.__hmrRevision;
                    if (window.__hmrEvaluatedRevision !== revision) return;
                    // React refresh runs synchronously after these hooks resolve.
                    setTimeout(() => {
                        window.__hmrCompletedRevision = revision;
                        window.__hmrLastActivity = Date.now();
                    }, 0);
                });
            }""")
            source = project / "src/settings" / source_name
            original = source.read_text()
            for revision in range(3):
                page.evaluate("revision => { window.__hmrRevision = revision; }", revision)
                with page.expect_console_message(
                    predicate=lambda message: "[vite] hot updated:" in message.text,
                ):
                    source.write_text(original + f"\nwindow.__hmrEvaluatedRevision = {revision};\n")
                page.wait_for_function("window.__hmrEvaluatedRevision === window.__hmrRevision")
                if burst and revision < 2:
                    continue
                # Wait for this revision's refresh and subsequent invalidations,
                # not an unrelated API/state commit or a previous load event.
                page.wait_for_function("""() =>
                    window.__hmrCompletedRevision === window.__hmrRevision
                    && window.__hmrPendingBatches === 0
                    && Date.now() - window.__hmrLastActivity >= 500
                """)
                assert errors == [], errors
                expect(sources).to_be_visible()
                expect(page.get_by_role("tab", name="Data and Sync", exact=True)).to_have_attribute(
                    "aria-selected", "true",
                )
            assert unexpected_requests == []
            assert mutations == []
        finally:
            browser.close()

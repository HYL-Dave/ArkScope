"""Financial policy and paused-scope recovery in real, offline browser surfaces."""

import json

import pytest

from tests.test_sa_acquisition_popup import state
from tests.test_sa_article_settings_browser import HTML, ROOT, settings_origin
from tests.test_sa_body_repair_popup_layout import INIT


@pytest.mark.parametrize("locale,width", [("en", 1440), ("zh-Hant", 1440), ("en", 390), ("zh-Hant", 390)])
def test_financial_settings_layout_and_zero_save(settings_origin, locale, width, tmp_path):
    from playwright.sync_api import sync_playwright

    defaults = {"parser_failure_ticker_threshold": 3}
    view = {"values": defaults.copy(), "defaults": defaults, "setting_source": "default", "error_code": None}
    calls, errors = [], []
    html = HTML.replace("SAArticleAcquisitionSection", "SAFinancialAcquisitionSection")

    def route(request):
        url = request.request.url
        assert url.startswith(settings_origin), "unexpected external traffic"
        if "/__financial_settings" in url:
            request.fulfill(status=200, content_type="text/html", body=html)
        elif url.endswith("/sa/financial-acquisition-settings"):
            calls.append(request.request.method)
            if request.request.method == "PUT":
                view.update(values=request.request.post_data_json, setting_source="profile")
            request.fulfill(json=view)
        else:
            request.continue_()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.route("**/*", route)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(settings_origin + "/__financial_settings?locale=" + locale)
        page.locator('input[type="number"]').wait_for()
        assert page.locator('input[type="number"]').input_value() == "3"
        assert calls == ["GET"]
        page.locator('input[type="number"]').fill("0")
        save = page.get_by_role("button", name="Save financial capture settings" if locale == "en" else "儲存財報擷取設定", exact=True)
        save.click()
        page.wait_for_function("document.querySelector('.data-route-actions button:nth-child(2)').disabled")
        assert view["values"] == {"parser_failure_ticker_threshold": 0}
        assert calls == ["GET", "PUT"]
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        assert page.locator(".sa-article-settings").evaluate("""root=>[...root.querySelectorAll('label,input,button')].every(n=>{
          const r=n.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&n.scrollWidth<=n.clientWidth+1;})""")
        page.screenshot(path=str(tmp_path / f"financial-settings-{locale}-{width}.png"), full_page=True)
        assert errors == []
        browser.close()


@pytest.mark.parametrize("width", [320, 390])
def test_parser_pause_popup_and_resume_fit(width, tmp_path):
    from playwright.sync_api import sync_playwright

    snapshot = state()
    snapshot["paused_reason"] = "sa_company_layout_unrecognized"
    snapshot["pending_count"] = 951
    override = """
      const financialState=SNAPSHOT, previousSend=chrome.runtime.sendMessage;
      chrome.runtime.sendMessage=(message,callback)=>{
        if(!['get_company_refresh','resume_company_parser'].includes(message.action))return previousSend(message,callback);
        sent.push(message);
        if(message.action==='resume_company_parser')financialState.paused_reason=null;
        const value=JSON.parse(JSON.stringify(financialState));
        if(callback)queueMicrotask(()=>callback(value));
        return Promise.resolve(value);
      };
    """.replace("SNAPSHOT", json.dumps(snapshot))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": width, "height": 900})
        context.route("http**/*", lambda route: route.abort())
        context.add_init_script(INIT + override)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto((ROOT / "extensions/sa_alpha_picks/popup.html").as_uri())
        resume = page.get_by_role("button", name="Continue other financial scopes", exact=True)
        resume.wait_for()
        assert "sa_company_layout_unrecognized" in page.locator("#saAcquisitionWarning").inner_text()
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        page.screenshot(path=str(tmp_path / f"financial-parser-popup-{width}.png"), full_page=True)
        resume.click()
        page.wait_for_function("document.querySelector('#saAcquisitionResume').hidden")
        assert page.evaluate("sent.filter(m=>m.action==='resume_company_parser')") == [{"action": "resume_company_parser", "expected_generation": 7}]
        assert errors == []
        context.close()
        browser.close()

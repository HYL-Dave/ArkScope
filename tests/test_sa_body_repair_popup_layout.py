"""Isolated, offline Chromium layout check for the extension popup."""

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
INIT = r"""
(() => {
  const listeners = [];
  const data = {alphaPicksAutoSyncEnabled:true, marketNewsAutoSyncEnabled:true};
  const targets = Array.from({length:5}, (_,i) => ({article_id:String(1000+i),
    title:i === 0 ? 'LongTitleWithoutSpaces'.repeat(7) : 'Article '+(i+1)+' with a longer retained title'}));
  function reply(message) {
    if (message.action === 'get_article_body_recovery_state') return {status:'ok',batch:globalThis.fixtureBatch || null};
    if (message.action === 'preview_article_body_recovery') return {status:'ok',manifest_id:'offline',
      as_of:'2026-09-25',remaining_count:129,targets};
    if (message.action === 'start_article_body_recovery') return {status:'ok',batch:{
      status:'running',batch_id:'offline-batch',counts:{saved:1,failed:0,skipped:0,pending:4},
      next_page_at:new Date(Date.now()+60000).toISOString(),
      items:targets.map((t,i) => ({...t,state:i === 0 ? 'saved' : 'queued'}))}};
    if (message.action === 'cancel_article_body_recovery') return {status:'ok',batch:{
      status:'cancelled',batch_id:'offline-batch',counts:{saved:0,failed:1,skipped:0},
      items:targets.map(t => ({...t,state:'failed',reason:'article_context_changed'}))}};
    if (message.action === 'get_company_refresh') return {status:'ok',running:false,scopes:[],
      config:{enabled:false,target_mode:'watchlist',tickers:[],statements:['income_statement'],views:['annual'],interval_days:7},
      collector:{status:'ok',generation:0,owner:null,policy:null}};
    if (message.action === 'preview_company_refresh') return {status:'error'};
    if (message.action === 'get_extension_action_limits') return {status:'error'};
    if (message.action === 'market_news_recovery_preview') return {status:'no_work',can_start:false,target_count:0};
    return {status:'ok',events:[],total:0};
  }
  globalThis.chrome = {
    runtime:{lastError:null,onMessage:{addListener() {}},sendMessage(message,callback) {
      const value = reply(message);
      if (callback) queueMicrotask(() => callback(value));
      return Promise.resolve(value);
    }},
    storage:{local:{get(keys,callback) {
      const value = Object.fromEntries((Array.isArray(keys) ? keys : [keys]).map(k => [k,data[k]]));
      if (callback) queueMicrotask(() => callback(value));
      return Promise.resolve(value);
    },async set(values) {
      const changed = Object.fromEntries(Object.entries(values).map(([k,v]) => [k,{newValue:v}]));
      Object.assign(data,values); listeners.forEach(fn => fn(changed,'local'));
    }},onChanged:{addListener(fn) {listeners.push(fn);}}},
  };
})();
"""


@pytest.mark.parametrize("width", [340, 400])
def test_body_repair_popup_offline_layout(width, tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as instance:
        browser = instance.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": width, "height": 900})
        # Local extension assets only; no website or installed browser is touched.
        context.route("http**/*", lambda route: route.abort())
        context.add_init_script(INIT)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto((ROOT / "extensions/sa_alpha_picks/popup.html").as_uri())
        page.wait_for_function("document.querySelector('#bodyRecoveryStartBtn').disabled === false")
        assert page.locator("#bodyRecoveryTargets li").count() == 5
        assert "129 remaining" in page.locator("#bodyRecoveryPreview").inner_text()
        for state in ("preview", "waiting", "extracting", "cancelled"):
            if state == "waiting":
                page.locator("#bodyRecoveryStartBtn").click()
                assert "Waiting" in page.locator("#bodyRecoveryTiming").inner_text()
                assert page.locator("#bodyRecoveryProgress").evaluate("node=>node.value") == 1
                assert page.locator("#bodyRecoveryTargets").is_hidden()
                assert page.locator("#bodyRecoveryTiming").bounding_box()["y"] < page.locator("#bodyRecoveryResult").bounding_box()["y"]
            elif state == "extracting":
                page.evaluate("""() => chrome.storage.local.set({saArticleBodyRecovery:{
                  status:'running',batch_id:'offline-batch',counts:{saved:1,failed:0,skipped:0,pending:1},
                  items:[{article_id:'1000',title:'Saved article',state:'saved'},
                    {article_id:'1001',title:'LongTitleWithoutSpaces'.repeat(7),state:'running',phase:'extracting'}]
                }})""")
                assert "Reading article text" in page.locator("#bodyRecoveryTiming").inner_text()
            elif state == "cancelled":
                page.locator("#bodyRecoveryCancelBtn").click()
                page.wait_for_function("document.querySelector('#bodyRecoveryResult').textContent.includes('cancelled')")
            issues = page.evaluate(r"""() => {
              const root = document.querySelector('section[aria-labelledby="bodyRecoveryHeading"]');
              const failures = [];
              if (document.documentElement.scrollWidth > innerWidth) failures.push('horizontal overflow');
              for (const node of root.querySelectorAll('button,li,p,div,ol')) {
                if (node.scrollWidth > node.clientWidth + 1) failures.push('clipped text: '+node.id);
                const r = node.getBoundingClientRect();
                if (r.left < 0 || r.right > innerWidth) failures.push('outside viewport: '+node.id);
              }
              const buttons = [...root.querySelectorAll('button')].map(n => n.getBoundingClientRect());
              for (let i=0; i<buttons.length; i++) for (let j=i+1; j<buttons.length; j++) {
                const a=buttons[i], b=buttons[j];
                if (a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom)
                  failures.push('button overlap');
              }
              const next = root.nextElementSibling.getBoundingClientRect();
              if (root.getBoundingClientRect().bottom > next.top) failures.push('section overlap');
              return failures;
            }""")
            assert issues == []
            page.screenshot(path=str(tmp_path / f"popup-{width}-{state}.png"), full_page=True)
        assert errors == []
        assert page.locator("#alphaPicksAutoSyncToggle").is_checked()
        assert page.locator("#marketNewsAutoSyncToggle").is_checked()
        page.add_init_script("""globalThis.fixtureBatch={status:'running',batch_id:'persisted',
          next_page_at:new Date(Date.now()+60000).toISOString(),counts:{saved:1,pending:1},
          items:[{article_id:'1000',title:'Saved article',state:'saved'},
            {article_id:'1001',title:'Next article',state:'queued'}]};""")
        page.reload()
        page.wait_for_function("document.querySelector('#bodyRecoveryTiming').textContent.includes('Waiting')")
        assert page.locator("#bodyRecoveryStartBtn").is_disabled()
        assert page.locator("#bodyRecoveryTargets").is_hidden()
        assert page.locator("#bodyRecoveryTiming").evaluate("""node=>{
          const rect=node.getBoundingClientRect();return rect.top>=0 && rect.bottom<=innerHeight;
        }""")
        page.screenshot(path=str(tmp_path / f"popup-{width}-reopened.png"), full_page=True)
        assert errors == []
        context.close()
        browser.close()

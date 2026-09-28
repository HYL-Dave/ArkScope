"""Offline popup commands and durable progress at real popup widths."""

from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
INIT = r"""
(() => {
  const listeners = [], data = {alphaPicksAutoSyncEnabled:true, marketNewsAutoSyncEnabled:true};
  globalThis.sent = [];
  globalThis.fixtureReply = {status:'ok',protocol_version:2,state:'not_started'};
  const targets = Array.from({length:8}, (_,i) => ({article_id:String(1000+i),
    title:i === 0 ? 'LongTitleWithoutSpaces'.repeat(7) : 'Article '+(i+1)+' with a retained title'}));
  globalThis.job = (state, more={}) => ({status:'ok',protocol_version:2,job_id:'offline-job',revision:1,state,
    counts:{selected:129,saved:1,failed:0,skipped:0,pending:128},items:targets.map(t=>({...t,state:'pending'})),...more});
  function reply(message) {
    if (message.action === 'get_article_body_recovery_state') return fixtureReply;
    if (message.action === 'preview_article_body_recovery') return {status:'ok',protocol_version:2,manifest_id:'offline',
      as_of:'2026-09-28',counts:{targets:129,held:4,excluded:3},settings:{max_articles_per_job:0},targets};
    if (message.action === 'start_article_body_recovery') return fixtureReply=job('waiting',{
      reason_code:'site_pacing',next_eligible_at:new Date(Date.now()+60000).toISOString()});
    if (message.action === 'cancel_article_body_recovery') return fixtureReply=job('cancelling',{cancel_pending:true});
    if (message.action === 'resume_article_body_recovery') return fixtureReply=job('pending');
    if (message.action === 'get_company_refresh') return {status:'ok',running:false,scopes:[],
      config:{enabled:false,target_mode:'watchlist',tickers:[],statements:['income_statement'],views:['annual'],interval_days:7},
      collector:{status:'ok',generation:0,owner:null,policy:null}};
    if (message.action === 'preview_company_refresh' || message.action === 'get_extension_action_limits') return {status:'error'};
    if (message.action === 'market_news_recovery_preview') return {status:'no_work',can_start:false,target_count:0};
    return {status:'ok',events:[],total:0};
  }
  globalThis.chrome = {
    runtime:{lastError:null,onMessage:{addListener() {}},sendMessage(message,callback) {
      sent.push(message); const value = reply(message);
      if (callback) queueMicrotask(() => callback(value)); return Promise.resolve(value);
    }},
    storage:{local:{get(keys,callback) {
      const value = Object.fromEntries((Array.isArray(keys) ? keys : [keys]).map(k => [k,data[k]]));
      if (callback) queueMicrotask(() => callback(value)); return Promise.resolve(value);
    },async set(values) {
      const changed = Object.fromEntries(Object.entries(values).map(([k,v]) => [k,{newValue:v}]));
      Object.assign(data,values); listeners.forEach(fn => fn(changed,'local'));
    }},onChanged:{addListener(fn) {listeners.push(fn);}}},
  };
  globalThis.showJob = async (state,more={}) => {
    fixtureReply=job(state,more);
    await chrome.storage.local.set({saArticleBodyRecoveryV2:{job_id:'offline-job'}});
  };
})();
"""


@pytest.mark.parametrize("width", [320, 390])
def test_body_repair_popup_offline_layout(width, tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as instance:
        browser = instance.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": width, "height": 900})
        context.route("http**/*", lambda route: route.abort())
        context.add_init_script(INIT)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto((ROOT / "extensions/sa_alpha_picks/popup.html").as_uri())
        page.wait_for_function("document.querySelector('#bodyRecoveryStartBtn').disabled === false", timeout=3000)
        assert "Start repair" == page.locator("#bodyRecoveryStartBtn").inner_text()
        assert "129 selected" in page.locator("#bodyRecoveryPreview").inner_text()
        assert "4 held" in page.locator("#bodyRecoveryPreview").inner_text()
        assert page.evaluate("sent.filter(x=>x.action==='start_article_body_recovery').length") == 0
        for state in ("preview", "waiting", "paused", "pending", "cancelling", "partial", "complete"):
            if state == "waiting":
                page.locator("#bodyRecoveryStartBtn").click()
                assert "Waiting" in page.locator("#bodyRecoveryTiming").inner_text()
                assert page.locator("#bodyRecoveryProgress").evaluate("n=>n.max") == 129
                assert page.locator("#bodyRecoveryProgress").evaluate("n=>n.value") == 1
                assert page.locator("#bodyRecoveryStartBtn").is_disabled()
            elif state == "paused":
                page.evaluate("showJob('paused',{reason_code:'login_required'})")
                page.wait_for_function("!document.querySelector('#bodyRecoveryResumeBtn').hidden")
                assert "login" in page.locator("#bodyRecoveryTiming").inner_text().lower()
            elif state == "pending":
                page.locator("#bodyRecoveryResumeBtn").click()
                page.wait_for_function("document.querySelector('#bodyRecoveryResult').textContent.includes('pending')")
                assert page.evaluate("sent.some(x=>x.action==='resume_article_body_recovery'&&x.job_id==='offline-job')")
            elif state == "cancelling":
                page.locator("#bodyRecoveryCancelBtn").click()
                assert "Cancellation pending" in page.locator("#bodyRecoveryTiming").inner_text()
                assert page.evaluate("sent.some(x=>x.action==='cancel_article_body_recovery'&&x.job_id==='offline-job')")
                assert page.locator("#bodyRecoveryStartBtn").is_disabled()
            elif state in ("partial", "complete"):
                page.evaluate("state=>showJob(state,{counts:{selected:129,saved:state==='complete'?129:128,failed:state==='partial'?1:0,skipped:0,pending:0}})", state)
                page.wait_for_function("state=>document.querySelector('#bodyRecoveryResult').textContent.includes(state)", arg=state)
                assert page.locator("#bodyRecoveryStartBtn").is_disabled(), "fresh preview required"
                assert page.locator("#bodyRecoveryTiming").is_hidden()
            page.evaluate("() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
            issues = page.evaluate(r"""() => {
              const root=document.querySelector('section[aria-labelledby="bodyRecoveryHeading"]'), failures=[];
              if (document.documentElement.scrollWidth>innerWidth) failures.push('horizontal overflow');
              const visible=[...root.querySelectorAll('button,li,p,div,ol')].filter(n=>n.getClientRects().length);
              for (const node of visible) {
                if(node.scrollWidth>node.clientWidth+1) failures.push('clipped: '+node.id);
                const r=node.getBoundingClientRect(); if(r.left<0||r.right>innerWidth) failures.push('outside: '+node.id);
              }
              const buttons=visible.filter(n=>n.tagName==='BUTTON').map(n=>n.getBoundingClientRect());
              for(let i=0;i<buttons.length;i++) for(let j=i+1;j<buttons.length;j++) {
                const a=buttons[i],b=buttons[j];if(a.left<b.right&&b.left<a.right&&a.top<b.bottom&&b.top<a.bottom) failures.push('overlap');
              }
              if(root.getBoundingClientRect().bottom>root.nextElementSibling.getBoundingClientRect().top) failures.push('section overlap');
              return failures;
            }""")
            assert issues == []
            page.locator('[aria-labelledby="bodyRecoveryHeading"]').screenshot(path=str(tmp_path / f"popup-{width}-{state}.png"))
        assert page.locator("#alphaPicksAutoSyncToggle").is_checked()
        assert page.locator("#marketNewsAutoSyncToggle").is_checked()
        assert errors == []
        page.evaluate("""() => {fixtureReply={status:'ok',state:'not_started',legacy_history:{status:'partial'}};
          return chrome.storage.local.set({saArticleBodyRecoveryV2:{}}); }""")
        page.wait_for_function("document.querySelector('#bodyRecoveryResult').textContent.includes('Legacy history')")
        page.evaluate("""() => {fixtureReply={status:'error',error_code:'sa_body_upgrade_required'};
          return chrome.storage.local.set({saArticleBodyRecoveryV2:{}}); }""")
        page.wait_for_function("document.querySelector('#bodyRecoveryResult').textContent.includes('sa_body_upgrade_required')")
        assert page.locator("#bodyRecoveryStartBtn").is_disabled()
        context.close()
        browser.close()

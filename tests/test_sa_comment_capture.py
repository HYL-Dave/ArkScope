"""Comment controls and article identity, with no live SA access."""

from __future__ import annotations

import json
import os
import subprocess

import pytest

from tests.test_sa_extension_reconciliation_flow import ROOT, _run_background, _DETAIL_FLOW_SETUP


DOM_RUNNER = r"""
const {JSDOM, VirtualConsole}=require('jsdom');
const vm=require('node:vm');
const input=JSON.parse(process.argv[1]);
const dom=new JSDOM(input.html, {
  url:'https://seekingalpha.com/alpha-picks/articles/123456-test',
  runScripts:'outside-only', pretendToBeVisual:true, virtualConsole:new VirtualConsole(),
});
const w=dom.window;
Object.defineProperty(w.HTMLElement.prototype,'innerText',{get(){return this.textContent || '';}});
Object.defineProperty(w.HTMLElement.prototype,'offsetParent',{get(){return this.hidden ? null : this.parentElement;}});
w.HTMLElement.prototype.getBoundingClientRect=function(){return {top:input.top ?? 700,width:100,height:30};};
Object.defineProperty(w.document.body,'scrollHeight',{value:1000});
w.scrollBy=()=>{};
w.clicked=[];
w.document.addEventListener('click',event=>{
  w.clicked.push(event.target.id); event.preventDefault();
});
const context=dom.getInternalVMContext();
const result=vm.runInContext('('+input.func+')',context)(...(input.args || []));
process.stdout.write(JSON.stringify({result,clicked:w.clicked}));
"""


def _round(html: str, *, strategy="guarded", top=700):
    injected = _run_background(
        r"""
        let injected;
        sleep=async()=>{};
        chrome.scripting.executeScript=async request=>{
          if (!injected) injected={func:request.func.toString(),args:request.args || []};
          return [{result:{comments:0,atBottom:true,clicked:false,loading:false}}];
        };
        await scrollToComments(1,{mode:'quick',articleId:'123456'});
        return injected;
        """
    )
    if injected["args"]:
        injected["args"][0]["strategy"] = strategy
    result = subprocess.run(
        ["node", "-e", DOM_RUNNER, json.dumps(dict(injected, html=html, top=top))],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def _thread(control: str):
    return (
        '<div class="paywall-full-content"><article><p>Article prose.</p></article>'
        '<section><h3>Comments (2)</h3>'
        '<div class="border-t-share-separator-thin"><div class="break-words">Reply body</div>'
        + control + '</div></section></div>'
    )


def _observed_reply_footer(control: str):
    # Structural projection of 6338740's passive Firefox export, no SA prose.
    replies = ''.join(
        '<div><div class="flex border-t border-t-share-separator-thin pl-52">'
        f'<div class="break-words">Fixture reply {i}</div></div></div>' for i in range(3)
    )
    return (
        '<div class="paywall-full-content"><article>Unrelated article content</article>'
        '<div><h3>Comments (107)</h3></div><div><div id="thread">'
        '<div id="parent" class="flex border-t border-t-share-separator-thin">Parent</div>'
        '<div class="print:block">' + replies
        + '<div class="mb-18 ml-52">' + control + '</div></div></div></div></div>'
    )


def test_scan_reports_document_geometry_without_extra_scrolls_or_clicks():
    result = _round(_thread(''))
    assert result["clicked"] == []
    assert result["result"]["progress"] == {
        "scroll_y_before": 0, "scroll_y_after": 0,
        "document_height": 1000, "viewport_height": 768,
    }


@pytest.mark.parametrize("top", [100, 700])
def test_observed_sa_sibling_reply_footer_is_recognized_above_or_below_page_midpoint(top):
    result = _round(_observed_reply_footer('<button id="reply" type="button">See More Replies</button>'), top=top)
    assert result["clicked"] == ["reply"]
    audit = result["result"]["control_audit"]
    assert audit["guarded_candidates"] == 1
    assert audit["unresolved_candidates"] == 0
    assert audit["items"][0]["in_comment_scope"] is True


@pytest.mark.parametrize("top,clicked", [(100, []), (700, ["reply"])])
def test_observation_preserves_the_legacy_midpoint_selection(top, clicked):
    html = _observed_reply_footer('<button id="reply" type="button">See More Replies</button>')
    assert _round(html, strategy="observe", top=top)["clicked"] == clicked


@pytest.mark.parametrize("label", ["See More Replies", "View newest replies"])
@pytest.mark.parametrize("top", [100, 700])
def test_recognizable_reply_intent_outside_known_structure_is_unresolved(label, top):
    html = '<div class="paywall-full-content"><button id="unknown" type="button">' + label + '</button></div>'
    result = _round(html, top=top)
    assert result["clicked"] == []
    audit = result["result"]["control_audit"]
    assert audit["unresolved_candidates"] == 1
    assert audit["items"][0]["reason"] == "outside_comment_controls"


@pytest.mark.parametrize("old,new", [
    ('class="print:block"', 'class="new-layout"'),
    ('id="parent" class="flex border-t border-t-share-separator-thin"', 'id="parent"'),
    ('border-t-share-separator-thin pl-52', 'different-row pl-52'),
])
def test_changed_reply_footer_structure_is_not_authorized_by_label_alone(old, new):
    html = _observed_reply_footer('<button id="reply" type="button">See More Replies</button>').replace(old, new)
    result = _round(html)
    assert result["clicked"] == []
    assert result["result"]["control_audit"]["unresolved_candidates"] == 1


@pytest.mark.parametrize("control", [
    '<a id="unsafe" href="/article/999-other">See More Replies</a>',
    '<a id="unsafe" role="button" href="/article/999-other">See More Replies</a>',
    '<a id="unsafe" href="#replies" target="_blank">See More Replies</a>',
    '<button id="unsafe" form="f">See More Replies</button>',
])
def test_observed_footer_does_not_bypass_navigation_and_form_guards(control):
    result = _round(_observed_reply_footer(control) + '<form id="f"></form>')
    assert result["clicked"] == []
    assert result["result"]["control_audit"]["unresolved_candidates"] == 1


def test_hidden_unrecognized_reply_control_does_not_claim_incomplete_capture():
    result = _round('<div class="paywall-full-content"><button hidden>See More Replies</button></div>')
    assert result["clicked"] == []
    assert result["result"]["control_audit"]["unresolved_candidates"] == 0


def test_nested_reply_control_is_unresolved_unless_an_accepted_ancestor_handles_it():
    result = _round(_thread('<div role="button">Actions <button type="button">See More Replies</button></div>'), top=100)
    assert result["clicked"] == []
    assert result["result"]["control_audit"]["unresolved_candidates"] == 1
    handled = _round(_observed_reply_footer('<button id="outer" type="button"><span role="button">See More Replies</span></button>'))
    assert handled["clicked"] == ["outer"]
    assert handled["result"]["control_audit"]["unresolved_candidates"] == 0


@pytest.mark.parametrize("label", ["See my comments on the earnings report", "Show more of my replies"])
def test_prose_links_do_not_turn_valid_comment_capture_into_unresolved(label):
    result = _round('<article><a href="/article/999-other">' + label + '</a></article>', top=100)
    assert result["clicked"] == []
    assert result["result"]["control_audit"]["unresolved_candidates"] == 0


@pytest.mark.parametrize("control", [
    '<a id="unsafe" href="/article/other">Show more replies</a>',
    '<a id="unsafe" role="button" href="/article/other">Show more replies</a>',
    '<a id="unsafe" href="/alpha-picks/articles/123456-test">Show more replies</a>',
    '<a id="unsafe" href="#replies" target="_blank">Show more replies</a>',
    '<form><button id="unsafe">Show more replies</button></form>',
    '<form id="f"></form><button id="unsafe" form="f">Show more replies</button>',
    '<form><button><span id="unsafe" role="button">Show more replies</span></button></form>',
])
def test_comment_round_does_not_click_navigation_or_submission(control):
    result = _round(_thread(control))
    assert result["clicked"] == []


def test_mixed_article_container_does_not_authorize_unrelated_show_button():
    result = _round(_thread('<button id="reply" type="button">Show 2 replies</button>')
                    + '<button id="unrelated" type="button">Show all analysis</button>')
    assert result["clicked"] == ["reply"]


@pytest.mark.parametrize("control", [
    '<button id="reply" type="button">Show more replies</button>',
    '<button id="reply" type="button">See More Replies</button>',
    '<a id="reply" role="button" href="#replies">Show 2 replies</a>',
    '<div id="reply" role="button">Load more comments</div>',
])
def test_recognized_inline_comment_controls_still_expand(control):
    assert _round(_thread(control))["clicked"] == ["reply"]


def test_same_dom_audit_records_rejected_legacy_candidate_without_clicking_it():
    result = _round(_thread('<a id="unsafe" href="/article/other">Show more replies</a>'))
    audit = result["result"].get("control_audit")
    assert audit is not None
    assert audit["legacy_candidates"] == 1
    assert audit["guarded_candidates"] == 0
    assert audit["items"][0]["reason"] == "link_navigation"
    assert audit["items"][0]["ancestors"][0]["classes"] == ["border-t-share-separator-thin"]
    assert result["clicked"] == []


def test_shadow_observation_keeps_legacy_clicks_and_reports_candidate_difference():
    result = _round(_thread('<a id="unsafe" href="/article/other">Show more replies</a>'),
                    strategy="observe")
    assert result["clicked"] == ["unsafe"]
    assert result["result"].get("control_audit", {}).get("guarded_candidates") == 0


def test_inline_comment_text_expansion_is_not_confused_with_a_reader_link():
    control = '<div class="break-words">Truncated text <button id="expand" type="button">Show more</button></div>'
    assert _round(_thread(control))["clicked"] == ["expand"]
    unsafe = '<div class="break-words">Text <a id="link" href="/article/999-other">Show more</a></div>'
    result = _round(_thread(unsafe))
    assert result["clicked"] == []
    assert result["result"]["control_audit"]["items"][0]["in_comment_scope"] is True


def test_nested_control_does_not_trigger_the_same_expansion_twice():
    result = _round(_thread('<button id="outer" type="button"><span id="inner" role="button">Show more replies</span></button>'))
    assert result["clicked"] == ["outer"]


def test_bounded_audit_still_counts_all_unresolved_controls():
    controls = ''.join(f'<button id="b{i}" type="button">Show more replies</button>' for i in range(70))
    clean = _round(_thread(controls))["result"]["control_audit"]
    assert clean["omitted_count"] == 6
    assert clean.get("unresolved_candidates") == 0
    unsafe = _round(_thread(controls + '<a href="/article/other">Show more replies</a>'))["result"]["control_audit"]
    assert unsafe.get("unresolved_candidates") == 1


EVENTS = r"""
function event() {
  const listeners=new Set();
  return {addListener:f=>listeners.add(f),removeListener:f=>listeners.delete(f),
    emit:(...args)=>Array.from(listeners).forEach(f=>f(...args)),size:()=>listeners.size};
}
chrome.tabs.onUpdated=event(); chrome.tabs.onRemoved=event(); chrome.tabs.onCreated=event();
"""


@pytest.mark.parametrize("event", [
    "chrome.tabs.onUpdated.emit(1,{url:'https://seekingalpha.com/article/other'})",
    "chrome.tabs.onUpdated.emit(1,{status:'loading'})",
    "chrome.tabs.onCreated.emit({id:2,openerTabId:1})",
    "chrome.tabs.onRemoved.emit(1)",
])
def test_navigation_watch_rejects_changes_and_cleans_up(event):
    result = _run_background(EVENTS + r"""
      const watch=SACommentCapture.watchNavigation(chrome.tabs,1,'https://seekingalpha.com/article/123-test');
    """ + event + r""";
      let code=null;
      try {watch.assert();} catch(e) {code=e.code;}
      const evidence=watch.evidence(); watch.close();
      return {code,evidence,listeners:chrome.tabs.onUpdated.size()+chrome.tabs.onRemoved.size()+chrome.tabs.onCreated.size()};
    """)
    assert result["code"] == "article_context_changed"
    assert result["evidence"]["event_count"] == 1
    assert result["listeners"] == 0


def test_navigation_watch_ignores_fragment_and_other_tabs():
    result = _run_background(EVENTS + r"""
      const watch=SACommentCapture.watchNavigation(chrome.tabs,1,'https://seekingalpha.com/article/123-test');
      chrome.tabs.onUpdated.emit(1,{url:'https://seekingalpha.com/article/123-test#comment'});
      chrome.tabs.onUpdated.emit(2,{status:'loading'});
      chrome.tabs.onCreated.emit({id:3,openerTabId:2});
      watch.assert(); watch.close(); return watch.evidence();
    """)
    assert result["event_count"] == 0


@pytest.mark.parametrize("mutation", [
    "dom.reconfigure({url:'https://seekingalpha.com/article/999-other'});",
    "w.dispatchEvent(new w.PageTransitionEvent('pagehide'));",
    "delete w.__arkCommentDocument;",
    "w.document.head.innerHTML='<link rel=canonical href=https://seekingalpha.com/article/999-other>';",
])
def test_document_witness_rejects_changed_document_or_identity(mutation):
    script = r"""
      const fs=require('node:fs'); const {JSDOM}=require('jsdom');
      const dom=new JSDOM('<p>body</p>',{url:'https://seekingalpha.com/article/123-test',runScripts:'outside-only'});
      const w=dom.window;
      w.eval(fs.readFileSync('extensions/sa_alpha_picks/comment_capture.js','utf8'));
      const probe=w.SACommentCapture.documentState;
      const before=probe({phase:'begin',articleId:'123',token:'test'});
      MUTATION
      const after=probe({phase:'check',articleId:'123',token:'test'});
      process.stdout.write(JSON.stringify({before,after}));
    """.replace("MUTATION", mutation)
    result = subprocess.run(["node", "-e", script], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["before"]["ok"] is True
    assert output["after"]["ok"] is False


@pytest.mark.parametrize("path", ["detail", "comments", "manual"])
@pytest.mark.parametrize("transition", ["during_comments", "after_capture"])
def test_all_persistence_paths_reject_invalid_capture(path, transition):
    result = _run_background("const realBegin=beginArticleCapture;\n" + _DETAIL_FLOW_SETUP + EVENTS + r"""
      beginArticleCapture=realBegin;
      chrome.scripting.executeScript=async request=>{
        if(request.args[0].phase==='end' && TRANSITION==='after_capture') {
          chrome.tabs.onUpdated.emit(1,{status:'loading'});
          return [{result:{ok:false}}];
        }
        return [{result:{ok:true}}];
      };
      injectCommentsScraper=async()=>{
        if(TRANSITION==='during_comments') chrome.tabs.onUpdated.emit(1,{status:'loading'});
        return {comments:[{comment_id:'1',comment_text:'Captured before final verification'}]};
      };
      cleanupCollectorTabs=registerCollectorTab=unregisterCollectorTab=safeRemoveTab=async()=>{};
      chrome.tabs.create=async()=>({id:1});
      sendNativeMessage2=async message=>{
        calls.push(message);
        if(message.action==='save_articles_meta') return {status:'ok',saved:1,
          need_content:PATH==='detail'?[{article_id:'123456',url:'https://seekingalpha.com/alpha-picks/articles/123456-test'}]:[],
          need_comments:PATH==='comments'?[{article_id:'123456',url:'https://seekingalpha.com/alpha-picks/articles/123456-test'}]:[]};
        return {status:'ok',ok:true,comment_scan_usable:true};
      };
      const diagnostics=SAExtensionDiagnostics.createCollector();
      const result=PATH==='manual'
        ? await doManualFetch([{symbol:'AMD',role:'entry',event_anchor_date:'2026-09-01',lineage_id:1,
          url:'https://seekingalpha.com/alpha-picks/articles/123456-test'}],diagnostics)
        : await doDetailFetch(1,[],'quick',diagnostics);
      return {result,calls,diagnostics:diagnostics.freeze(),listeners:chrome.tabs.onUpdated.size()};
    """.replace("PATH", json.dumps(path)).replace("TRANSITION", json.dumps(transition)))
    assert result["listeners"] == 0
    if transition == "after_capture":
        assert any(call["action"] in {"save_article_content", "save_comments_only"} for call in result["calls"])
        assert result["result"]["failed"] == 0
        return
    assert not any(call["action"] in {"save_article_content", "save_comments_only", "accept_reconciliation_link"}
                   for call in result["calls"])
    if path == "manual":
        assert not any(call["action"] == "save_articles_meta" for call in result["calls"])
    assert result["result"]["failed"] == 1
    assert result["diagnostics"]["entries"][0]["reason_code"] == "article_context_changed"


@pytest.mark.parametrize("browser_name", ["chromium", "firefox"])
@pytest.mark.skipif(os.environ.get("ARKSCOPE_BROWSER_ACCEPTANCE") != "1", reason="isolated installed-browser gate")
def test_real_browsers_preserve_expansion_and_detect_document_replacement(tmp_path, browser_name):
    from playwright.sync_api import sync_playwright
    from tests.sa_comment_acceptance.build import build

    package = tmp_path / "extension"
    build(package)
    url = "https://seekingalpha.com/article/123-fixture"
    html = """<!doctype html><html><body><h1>Fixture article</h1>
    <section><h3>Comments (2)</h3><div class="border-t-share-separator-thin">
    <div class="break-words"><span id="text">Initial comment.</span>
    <button type="button" id="expand" onclick="document.getElementById('text').textContent='Initial comment. Full text.';this.remove()">Show more</button></div>
    <form onsubmit="window.submissions++;return false"><button><span role="button">Show more replies</span></button></form>
    </div></section>""" + _observed_reply_footer(
        '<button type="button" id="footer" onclick="window.footerExpansions++;this.remove()">See More Replies</button>'
    ) + '<script>window.submissions=0;window.footerExpansions=0</script></body></html>'
    with sync_playwright() as pw:
        browser = getattr(pw,browser_name).launch(headless=True, proxy={"server":"http://127.0.0.1:9"})
        try:
            page = browser.new_page()
            page.route("**/*", lambda route:route.fulfill(body=html, content_type="text/html"))
            page.goto(url)
            page.add_script_tag(path=str(package / "comment_capture.js"))
            state = page.evaluate("SACommentCapture.documentState({phase:'begin',token:'one',articleId:'123'})")
            assert state["ok"] is True
            scan = page.evaluate("SACommentCapture.scanPage({strategy:'guarded',token:'one'})")
            assert scan["click_count"] == 2
            assert page.locator("#text").inner_text() == "Initial comment. Full text."
            assert page.evaluate("window.footerExpansions") == 1
            assert page.evaluate("window.submissions") == 0
            # Real reload replaces even a document with exactly the same URL.
            page.reload()
            page.add_script_tag(path=str(package / "comment_capture.js"))
            assert page.evaluate("SACommentCapture.documentState({phase:'check',token:'one',articleId:'123'}).ok") is False
            # Exercise the actual orchestration with DOM-backed executeScript.
            page.add_script_tag(path=str(package / "capture_driver.js"))
            scripts = {name:(package / name).read_text() for name in ("article_identity.js","scrape_detail.js","scrape_comments.js")}
            result = page.evaluate("""async scripts=>{
              function event(){return {addListener(){},removeListener(){}};}
              window.chrome={tabs:{onUpdated:event(),onRemoved:event(),onCreated:event()},
                scripting:{executeScript:async request=>{
                  if(request.func) return [{result:request.func(...(request.args || []))}];
                  let result;for(const file of request.files) result=(0,eval)(scripts[file]);
                  return [{result}];
                }}};
              settleArticleBeforeScroll=async()=>{};
              scrollToComments=async()=>({stop_reason:'stable_bottom'});
              injectCommentsScraper=async()=>{
                dispatchEvent(new PageTransitionEvent('pagehide'));
                return {comments:[{comment_text:'must not escape'}]};
              };
              try{await captureArticle(1,{article_id:'123',url:location.href},'manual',false);return 'escaped';}
              catch(e){return e.code;}
            }""",scripts)
            assert result == "article_context_changed"
        finally:
            browser.close()

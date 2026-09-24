"""Recent-comment priority and bounded traversal, without provider access."""

import json
import os
import subprocess

import pytest

from tests.test_sa_extension_reconciliation_flow import ROOT, _run_background


def dom_scan(html, *, scope="recent", at_bottom=False):
    script = r"""
    const fs=require('node:fs'), {JSDOM}=require('jsdom');
    const input=JSON.parse(process.argv[1]);
    const w=new JSDOM(input.html,{url:'https://seekingalpha.com/article/123-test',runScripts:'outside-only',pretendToBeVisual:true}).window;
    Object.defineProperty(w.HTMLElement.prototype,'innerText',{get(){return this.textContent || '';}});
    Object.defineProperty(w.HTMLElement.prototype,'offsetParent',{get(){return this.hidden ? null : this.parentElement;}});
    w.HTMLElement.prototype.getBoundingClientRect=function(){
      const top=Number(this.dataset.top || 700)-w.scrollY, height=Number(this.dataset.height || 30);
      return {top,bottom:top+height,height,width:100};
    };
    Object.defineProperty(w.document.body,'scrollHeight',{value:20000});
    w.scrollY=input.at_bottom?19500:0; w.innerHeight=500;
    w.scrollBy=(x,y)=>{w.scrollY=Math.min(19500,w.scrollY+y);};
    w.clicked=[];
    w.document.addEventListener('click',e=>{w.clicked.push(e.target.id);e.preventDefault();});
    w.eval(fs.readFileSync('extensions/sa_alpha_picks/scrape_comments.js','utf8'));
    w.eval(fs.readFileSync('extensions/sa_alpha_picks/comment_capture.js','utf8'));
    w.SACommentCapture.scanPage({scope:input.scope,nowMs:Date.parse('2026-09-24T12:00:00Z')})
      .then(result=>process.stdout.write(JSON.stringify({result,clicked:w.clicked})));
    """
    result = subprocess.run(["node", "-e", script, json.dumps(dict(html=html, scope=scope, at_bottom=at_bottom))],
                            cwd=ROOT, text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def row(name, date, *, control="Show more", top=700, text="A complete test comment"):
    return (f'<div class="border-t-share-separator-thin" data-top="{top}">'
            f'<a href="/user/{name}">{name}</a><time datetime="{date}">{date}</time>'
            f'<div class="break-words">{text}<button type="button" id="{name}">{control}</button></div></div>')


def test_recent_default_defers_old_text_but_preserves_unknown_and_new_replies():
    html = row("old", "2026-01-01T00:00:00Z") + row("recent", "2026-09-23T00:00:00Z")
    html += row("unknown", "unrecognized") + row("parent", "2026-01-01T00:00:00Z", control="See More Replies")
    result = dom_scan(html)
    assert result["clicked"] == ["recent", "unknown", "parent"]
    assert result["result"]["recency"]["recent_count"] == 1
    assert result["result"]["recency"]["unknown_date_count"] == 1
    assert result["result"]["recency"]["older_count"] == 2
    assert result["result"]["recency"]["deferred_historical_controls"] == 1
    assert result["result"]["control_audit"]["unresolved_candidates"] == 0


def test_history_is_explicit_and_still_expands_older_text():
    html = row("old", "2026-01-01T00:00:00Z")
    assert dom_scan(html, scope="history")["clicked"] == ["old"]
    assert dom_scan(html)["clicked"] == []


def test_date_is_per_reply_not_article_or_parent_and_old_row_is_not_a_stop():
    html = row("parent", "2026-01-01T00:00:00Z", text="Old context")
    html += row("reply", "2026-09-23T00:00:00Z", text="@parent A recent reply", top=2000)
    html += row("oldtail", "2026-01-02T00:00:00Z", top=9000)
    result = dom_scan(html)
    assert "reply" in result["clicked"]
    assert result["result"]["recency"]["recent_count"] == 1
    assert result["result"]["recency"]["coverage"] == "unverified"
    assert result["result"]["progress"]["scroll_y_after"] > 500
    assert result["result"]["atBottom"] is False


def test_loaded_prefix_uses_bounded_rendered_steps_not_a_jump_to_bottom():
    html = row("a", "2026-09-23T00:00:00Z", top=1500, control="")
    html += row("b", "2026-09-23T00:00:00Z", top=14000, control="")
    result = dom_scan(html)["result"]
    assert 500 < result["progress"]["scroll_y_after"] <= 8 * 500 * 0.75
    assert result["progress"]["scroll_y_after"] < 19500


def test_unknown_or_future_dates_do_not_become_old_or_prove_recent_coverage():
    result = dom_scan(row("future", "2027-09-23T00:00:00Z") + row("unknown", "bad"), at_bottom=True)
    assert result["clicked"] == ["future", "unknown"]
    assert result["result"]["recency"]["unknown_date_count"] == 2
    assert result["result"]["recency"]["coverage"] == "unverified"


def test_capture_intent_is_independent_of_initial_long_scroll_profile():
    result = _run_background(r"""
      const calls=[];
      beginArticleCapture=async()=>({assert:async()=>{},close:async()=>{}});
      settleArticleBeforeScroll=async()=>{};
      injectCommentsScraper=async()=>({comments:[]});
      scrollToComments=async(id,opts)=>{calls.push({scope:opts.scope,mode:opts.mode});return {};};
      await captureArticle(1,{article_id:'a',comment_scan_mode:'backfill'},'quick',false);
      await captureArticle(1,{article_id:'a'},'backfill',false);
      return calls;
    """)
    assert result == [{"scope": "recent", "mode": "backfill"}, {"scope": "history", "mode": "backfill"}]


def test_old_ancestors_and_already_loaded_history_are_retained_in_original_order():
    result = _run_background(r"""
      const comments=[
        {comment_id:'old',comment_date:'2026-01-01T00:00:00Z'},
        {comment_id:'parent',comment_date:'2026-01-01T00:00:00Z'},
        {comment_id:'reply',comment_date:'2026-09-22T00:00:00Z',parent_comment_id:'parent'},
        {comment_id:'unknown',comment_date:null}];
      return SACommentCapture.commentPolicy(comments,'recent',Date.parse('2026-09-24T12:00:00Z'));
    """)
    assert [c["comment_id"] for c in result["comments"]] == ["old", "parent", "reply", "unknown"]
    assert result["summary"]["context_count"] == 1


def test_quoted_date_inside_comment_text_cannot_determine_its_age():
    result = dom_scan(row("unknown", "bad", text="I bought on Jan 1, 2020, 3:00 PM"))
    assert result["clicked"] == ["unknown"]
    assert result["result"]["recency"]["unknown_date_count"] == 1


@pytest.mark.parametrize("date", ["9", "2026", "not a date"])
def test_non_datetime_attribute_is_not_guessed_as_an_old_publication(date):
    result = dom_scan(row("unknown", date))
    assert result["result"]["recency"]["unknown_date_count"] == 1
    assert result["clicked"] == ["unknown"]


@pytest.mark.parametrize("browser_name", ["chromium", "firefox"])
@pytest.mark.skipif(os.environ.get("ARKSCOPE_BROWSER_ACCEPTANCE") != "1", reason="isolated installed-browser gate")
def test_loaded_reply_height_does_not_consume_viewport_per_settle_budget(browser_name):
    from playwright.sync_api import sync_playwright

    # Same 71-round allowance as a 120s/1.6s scan, not a real-site timing claim.
    # The scroll listener represents a lazy-load frontier after materialized rows.
    html = """<style>article{height:4000px}.row{height:500px}</style>
    <article>Fixture article</article><section id="comments"><h3>Comments (180)</h3></section>
    <script>
      window.rows=0;window.batches=0;
      function appendBatch(){
        for(let i=0;i<60;i++){
          const row=document.createElement('div');row.className='row border-t-share-separator-thin';
          row.innerHTML='<time datetime="2026-09-23T00:00:00Z"></time><div class="break-words">Fixture comment '+(++rows)+'</div>';
          document.getElementById('comments').append(row);
        }batches++;
      }
      appendBatch();
      addEventListener('scroll',()=>{
        if(batches<3 && document.querySelector('#comments').lastElementChild.getBoundingClientRect().top<=innerHeight) appendBatch();
      });
    </script>"""
    with sync_playwright() as pw:
        browser = getattr(pw, browser_name).launch(headless=True, proxy={"server":"http://127.0.0.1:9"})
        try:
            page = browser.new_page(viewport={"width":1000,"height":995})
            page.route("**/*", lambda route: route.fulfill(body=html, content_type="text/html"))
            observations = {}
            for strategy in ("observe", "guarded"):
                page.goto("https://seekingalpha.com/article/123-fixture")
                for script in ("comment_capture.js", "scrape_comments.js"):
                    page.add_script_tag(path=str(ROOT / "extensions/sa_alpha_picks" / script))
                observations[strategy] = page.evaluate("""async strategy=>{
                  let bottom=0,result;
                  for(let i=0;i<71;i++){
                    result=await SACommentCapture.scanPage({strategy,scope:'recent',nowMs:Date.parse('2026-09-24T12:00:00Z')});
                    await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
                    bottom=result.atBottom?bottom+1:0;
                    if(bottom>=5) return {rows,rounds:i+1,terminal:true};
                  }
                  return {rows,rounds:71,terminal:false};
                }""", strategy)
            assert observations["guarded"]["rows"] == 180
            assert observations["guarded"]["terminal"] is True
            assert observations["observe"]["terminal"] is False
            assert observations["guarded"]["rounds"] < observations["observe"]["rounds"]
        finally:
            browser.close()


@pytest.mark.parametrize("browser_name", ["chromium", "firefox"])
@pytest.mark.skipif(os.environ.get("ARKSCOPE_BROWSER_ACCEPTANCE") != "1", reason="isolated installed-browser gate")
def test_materialized_reply_traversal_preserves_intermediate_intersection_observers(browser_name):
    from playwright.sync_api import sync_playwright

    html = '<style>.row{height:800px}</style><section id="comments">'
    for i in range(8):
        if i == 2:
            html += '<div id="sentinel" style="height:1px"></div>'
        html += f'<div class="row border-t-share-separator-thin"><div class="break-words">Fixture {i}</div></div>'
    html += """</section><script>
      new IntersectionObserver((entries,observer)=>{
        if(entries.some(entry=>entry.isIntersecting)){
          const row=document.createElement('div');row.className='row border-t-share-separator-thin';
          row.innerHTML='<div class="break-words">Loaded by intermediate sentinel</div>';
          document.getElementById('comments').append(row);observer.disconnect();
        }
      }).observe(document.getElementById('sentinel'));
    </script>"""
    with sync_playwright() as pw:
        browser = getattr(pw, browser_name).launch(headless=True, proxy={"server":"http://127.0.0.1:9"})
        try:
            page = browser.new_page(viewport={"width":1000,"height":995})
            page.route("**/*", lambda route: route.fulfill(body=html, content_type="text/html"))
            for strategy in ("observe", "guarded"):
                page.goto("https://seekingalpha.com/article/123-fixture")
                page.add_script_tag(path=str(ROOT / "extensions/sa_alpha_picks/comment_capture.js"))
                count = page.evaluate("""async strategy=>{
                  for(let i=0;i<20;i++){
                    await SACommentCapture.scanPage({strategy});
                    await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
                  }
                  return document.querySelectorAll('.row').length;
                }""", strategy)
                assert count == 9, strategy
        finally:
            browser.close()

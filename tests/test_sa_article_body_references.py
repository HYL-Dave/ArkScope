"""Reference preservation is distinct from image download or complete source text."""

from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
import subprocess
import threading

import pytest

from src import sa_capture_store as store
from src.sa.article_body_capture import encode_capture, reference_coverage, validate_capture
from src.sa.article_body_quality import assess_body, narrative_text
from src.sa.article_reader import read_article
from src.tools.backends.sa_capture_backend import SACaptureBackend
from tests.test_sa_extension_article_body import BODY, COMMENTS, EXTENSION, ROOT, _scrape
from tests.test_sa_article_acquisition_scope import scope_case


def manifest(**updates):
    return {"schema_version": 1, "extractor_version": 2,
            "links": {"observed": 2, "retained": 2},
            "images": {"observed": 1, "retained": 1}, "unsupported_embeds": 0, **updates}


def page(markup):
    return '<div data-test-id="article-body">' + BODY + markup + "</div>"


def render(markdown):
    result = subprocess.run(["node", str(ROOT / "tests/js/inspect_sa_article_markdown.mjs")],
                            input=markdown, capture_output=True, text=True, cwd=ROOT, check=True)
    return json.loads(result.stdout)


def test_article_keeps_links_images_captions_tables_and_source_order(tmp_path):
    result = _scrape(tmp_path, page(
        '<p>Before <a href="/source/report.pdf"><strong>Source Link</strong></a> after.</p>'
        '<figure><div><picture><source srcset="https://images.example/large.png 2x">'
        '<img src="https://images.example/chart.png" alt="Revenue [2026]"></picture></div>'
        '<figcaption>Chart explanation, not numeric OCR.</figcaption></figure>'
        '<table><tr><th>Metric</th><th>Source</th></tr>'
        '<tr><td>12 | 18</td><td><a href="https://issuer.example/results">Report</a></td></tr></table>'
    ))
    text = result["body_markdown"]
    assert "Before [Source Link](<https://seekingalpha.com/source/report.pdf>) after." in text
    assert "![Revenue \\[2026\\]](<https://images.example/chart.png>)" in text
    assert text.count("Chart explanation, not numeric OCR.") == 1
    assert "| 12 \\| 18 | [Report](<https://issuer.example/results>) |" in text
    assert text.index("Before") < text.index("![Revenue") < text.index("Chart explanation") < text.index("| Metric")
    assert result["body_capture"] == manifest()
    rendered = render(text)
    assert rendered["tables"] == [[["Metric", "Source"], ["12 | 18", "Report"]]]
    assert rendered["images"] == [{"src": "https://images.example/chart.png", "alt": "Revenue [2026]", "title": ""}]
    assert [link["href"] for link in rendered["links"]] == ["https://seekingalpha.com/source/report.pdf", "https://issuer.example/results"]


@pytest.mark.parametrize("source", [
    'src="data:image/gif;base64,AAAA" data-src="https://images.example/lazy.png"',
    'data-original="https://images.example/lazy.png"',
    'data-lazy-src="https://images.example/lazy.png"',
])
def test_unloaded_image_retains_explicit_lazy_reference_without_loading(tmp_path, source):
    result = _scrape(tmp_path, page(f'<figure><img {source} alt="Not loaded yet"></figure>'))
    assert "![Not loaded yet](<https://images.example/lazy.png>)" in result["body_markdown"]
    assert result["body_capture"]["images"] == {"observed": 1, "retained": 1}


@pytest.mark.parametrize("url", [
    "javascript:alert(1)", "data:text/html,bad", "file:///tmp/private", "blob:https://seekingalpha.com/private",
    "https://user:password@issuer.example/private", "java&#10;script:alert(1)", "",
])
def test_unsafe_or_missing_reference_keeps_label_but_not_url(tmp_path, url):
    result = _scrape(tmp_path, page(f'<p><a href="{url}">Source Link</a></p><img src="{url}" alt="Chart">'))
    assert "Source Link" in result["body_markdown"]
    assert "[Source Link](" not in result["body_markdown"]
    assert "[Image reference unavailable: Chart]" in result["body_markdown"]
    assert result["body_capture"]["links"] == result["body_capture"]["images"] == {"observed": 1, "retained": 0}
    assert "password" not in result["body_markdown"]


def test_http_image_is_not_embedded_and_relative_urls_ignore_base_tag(tmp_path):
    result = _scrape(tmp_path, '<base href="https://wrong.example/">' + page(
        '<a href="/source">Source</a><img src="http://images.example/chart.png" alt="Chart">'
    ))
    assert "[Source](<https://seekingalpha.com/source>)" in result["body_markdown"]
    assert "wrong.example" not in result["body_markdown"]
    assert result["body_capture"]["images"] == {"observed": 1, "retained": 0}


def test_linked_image_and_escaped_labels_do_not_create_extra_links(tmp_path):
    result = _scrape(tmp_path, page(
        '<a href="https://images.example/full(a).png"><img src="https://images.example/small.png" '
        'alt="x](javascript:bad) ![y]"></a>'
    ))
    text = result["body_markdown"]
    assert r"x\](javascript:bad) \!\[y\]" in text
    assert "[![" in text and "](<https://images.example/full(a).png>)" in text
    assert result["body_capture"]["images"] == result["body_capture"]["links"] == {"observed": 1, "retained": 1}
    rendered = render(text)
    assert rendered["images"][0]["alt"] == "x](javascript:bad) ![y]"
    assert rendered["links"] == [{"text": "", "href": "https://images.example/full(a).png"}]


def test_image_title_retained_separately_from_alt_and_caption(tmp_path):
    result = _scrape(tmp_path, page(
        '<figure><img src="https://images.example/chart.png" alt="Revenue chart" '
        'title="Management &quot;outlook&quot; \\ FY2026"><figcaption>Caption evidence</figcaption></figure>'
    ))
    assert render(result["body_markdown"])["images"] == [{
        "src": "https://images.example/chart.png", "alt": "Revenue chart", "title": 'Management "outlook" \\ FY2026',
    }]
    assert result["body_markdown"].count("Caption evidence") == 1


def test_table_caption_resources_are_retained_and_not_just_counted(tmp_path):
    result = _scrape(tmp_path, page(
        '<table><caption>Evidence <a href="https://issuer.example/report">Source</a>'
        '<img src="https://images.example/figure.png" alt="Figure"></caption>'
        '<tr><th>Revenue</th></tr><tr><td>10</td></tr></table>'
    ))
    rendered = render(result["body_markdown"])
    assert rendered["links"] == [{"text": "Source", "href": "https://issuer.example/report"}]
    assert rendered["images"][0]["src"] == "https://images.example/figure.png"
    assert result["body_capture"]["links"] == result["body_capture"]["images"] == {"observed": 1, "retained": 1}
    assert result["body_markdown"].index("Evidence") < result["body_markdown"].index("| Revenue")


def test_comment_ad_hidden_and_control_references_stay_excluded(tmp_path):
    excluded = '<a href="https://excluded.example/source">Unrelated source</a><img src="https://excluded.example/chart.png">'
    result = _scrape(tmp_path, page(
        '<aside>' + excluded + '</aside><div style="display:none">' + excluded + '</div>'
        '<button>' + excluded + '</button><div class="ad-banner">' + excluded + '</div>'
        '<div class="border-t-share-separator-thin">' + excluded + '</div>' + COMMENTS
    ))
    assert "excluded.example" not in result["body_markdown"]
    assert "Unrelated source" not in result["body_markdown"]
    assert result["body_capture"]["links"] == result["body_capture"]["images"] == {"observed": 0, "retained": 0}


def test_unresolved_srcset_and_embedded_graphics_are_visible_gaps(tmp_path):
    result = _scrape(tmp_path, page(
        '<img srcset="https://images.example/chart.png 2x" alt="Browser has not selected a source">'
        '<canvas></canvas><svg><text>Not extracted chart values</text></svg>'
        '<iframe src="https://issuer.example/chart"></iframe>'
    ))
    assert result["body_capture"]["images"] == {"observed": 1, "retained": 0}
    assert result["body_capture"]["unsupported_embeds"] == 3
    assert "Not extracted chart values" not in result["body_markdown"]
    assert result["body_markdown"].count("Embedded visual or media not captured") == 3


def test_market_news_path_does_not_gain_article_capture_claims(tmp_path):
    result = _scrape(tmp_path, page('<p>A retained paragraph with <a href="https://issuer.example/report">source</a> and further explanation.</p>'), news=True)
    assert result["body_capture"] is None
    assert "https://issuer.example/report" not in result["body_markdown"]


@pytest.fixture
def captured(tmp_path):
    path = tmp_path / "sa.db"
    with closing(store.connect(str(path))) as conn:
        conn.execute("INSERT INTO sa_articles(article_id,url,title,body_markdown) VALUES(?,?,?,?)",
                     ("123", "https://seekingalpha.com/alpha-picks/articles/123-analysis", "Provider article", None))
        conn.commit()
    return path, SACaptureBackend(sa_db=str(path), market_db=":memory:")


def test_repaired_resource_counts_follow_body_through_storage_and_pagination(captured):
    path, backend = captured
    text = ("Revenue grew as customers renewed their contracts. " * 20
            + "\n\n[Source](<https://issuer.example/report>) and [Data](<https://issuer.example/data>)"
            + "\n\n![Chart](<https://images.example/chart.png>)")
    result = backend.repair_article_body("123", text, expected_body_sha256=hashlib.sha256(b"").hexdigest(), body_capture=manifest())
    assert result["body_saved"] is True
    first = read_article(path, "123", body_limit=150, comment_limit=0)
    refs = first["coverage"]["references"]
    assert refs["status"] == "observed_references_retained"
    assert refs["image_storage"] == "remote_references_only"
    assert first["coverage"]["body"]["completeness"] == "not_verified"
    assert "image_pixels_not_stored_or_read_by_this_tool" in first["limitations"]
    pieces = [first["body_markdown"]]
    page_result = first
    while page_result["pagination"]["next_body_offset"] is not None:
        page_result = read_article(path, "123", body_offset=page_result["pagination"]["next_body_offset"],
                                   body_limit=150, comment_limit=0, snapshot_id=first["snapshot_id"])
        assert page_result["coverage"]["references"] == refs
        pieces.append(page_result["body_markdown"])
    assert "".join(pieces) == text
    assert backend.get_sa_article_with_comments("123")["body_references"] == refs
    listing = backend.query_sa_articles()[0]
    assert listing["body_references"] == refs and "body_capture_json" not in listing


def test_bad_or_old_body_metadata_never_claims_resources_preserved(captured):
    path, backend = captured
    body = "Captured prose remains available even if old metadata is absent."
    backend.save_article_with_comments("123", body, [], body_capture=manifest())
    first = read_article(path, "123", body_limit=10, comment_limit=0)
    with closing(store.connect(str(path))) as conn:
        conn.execute("UPDATE sa_articles SET body_capture_json=?", (encode_capture("other prose", manifest()),))
        conn.commit()
    result = read_article(path, "123")
    assert result["body_markdown"] == body
    assert result["coverage"]["references"]["status"] == "unavailable"
    assert read_article(path, "123", body_offset=10, snapshot_id=first["snapshot_id"])["error_code"] == "sa_article_snapshot_changed"
    backend.save_article_with_comments("123", body, [])
    assert read_article(path, "123")["coverage"]["references"]["status"] == "not_recorded"


def test_invalid_body_does_not_overwrite_good_body_or_resource_evidence(captured):
    path, backend = captured
    body = "The company has expanded its customer base and operating cash flows."
    backend.save_article_with_comments("123", body, [], body_capture=manifest())
    backend.save_article_with_comments("123", "# Provider article", [], body_capture={"broken": True})
    result = read_article(path, "123")
    assert result["body_markdown"] == body
    assert result["coverage"]["references"]["status"] == "observed_references_retained"
    skipped = backend.repair_article_body("123", body + " changed", expected_body_sha256=hashlib.sha256(body.encode()).hexdigest(), body_capture=manifest())
    assert skipped["reason"] == "already_present"


def test_pick_copy_only_uses_reference_evidence_for_its_own_body(captured):
    path, backend = captured
    from tests.test_sa_article_body_recovery import pick

    with closing(store.connect(str(path))) as conn:
        pick(conn, 1, canonical="123")
        conn.commit()
    old = 'Business demand improved.\n\n![Chart](<https://images.example/old.png>)'
    backend.save_article_with_comments("123", old, [], body_capture=manifest())
    result = backend.get_sa_pick_detail("KEEP")
    assert result["detail_report"] == old
    assert result["body_references"]["status"] == "observed_references_retained"
    newer = old.replace("old.png", "new.png")
    backend.save_article_with_comments("123", newer, [], body_capture=manifest())
    result = backend.get_sa_pick_detail("KEEP")
    assert result["detail_report"] == old
    assert result["body_references"]["status"] == "not_recorded"
    assert read_article(path, "123")["coverage"]["references"]["status"] == "observed_references_retained"


@pytest.mark.parametrize("mutate", [
    lambda m: m.update(schema_version=True), lambda m: m.update(extractor_version=999),
    lambda m: m.update(extra="untrusted"), lambda m: m.update(unsupported_embeds=-1),
    lambda m: m["images"].update(retained=2), lambda m: m["links"].update(observed=10001),
    lambda m: m["links"].update(retained=False), lambda m: m.update(images=[]),
])
def test_capture_contract_rejects_mutations_without_writing(captured, mutate):
    path, backend = captured
    value = deepcopy(manifest())
    mutate(value)
    with pytest.raises(ValueError, match="sa_article_body_capture_invalid"):
        backend.save_article_with_comments("123", "Actual business analysis.", [], body_capture=value)
    with closing(store.connect(str(path), read_only=True)) as conn:
        assert tuple(conn.execute("SELECT body_markdown,body_capture_json FROM sa_articles").fetchone()) == (None, None)


def test_partial_coverage_has_real_counts_and_missing_metadata_is_unknown():
    capture = manifest(images={"observed": 3, "retained": 1}, unsupported_embeds=1)
    assert validate_capture(capture) == capture
    coverage = reference_coverage("body", encode_capture("body", capture))
    assert coverage["status"] == "partial" and coverage["images"]["observed"] == 3
    assert reference_coverage("body", None) == {"status": "not_recorded", "image_storage": "unknown"}
    assert reference_coverage("body", json.dumps({"capture": capture}))["status"] == "unavailable"


@pytest.mark.parametrize("resources", [
    '![Chart](<https://images.example/chart.png> "Description")',
    '[![Chart](<https://images.example/chart.png>)](<https://issuer.example/source>)',
    '[Source Link](<https://issuer.example/data>)',
    '[Source Link](<https://issuer.example/data>).',
    '[Image reference unavailable: Revenue chart]',
    '[Embedded visual or media not captured]',
    '> [Embedded visual or media not captured]',
    '- ![Chart](<https://images.example/chart.png>)',
    '## ![Chart](<https://images.example/chart.png>)',
])
def test_resource_only_capture_cannot_be_promoted_to_narrative(resources):
    assert assess_body("# Article\n\n" + resources, title="Article")["status"] == "unusable"
    assert assess_body("Business demand improved.\n\n" + resources)["status"] == "available"


def test_linked_prose_remains_prose_but_destinations_and_image_labels_are_not_evidence():
    assert narrative_text('Cash flow [grew](<https://issuer.example/report>) this quarter.') == 'Cash flow grew this quarter.'
    from src.sa_article_reconciliation import ArticleEvidence, PickEvent, evaluate_candidate

    event = PickEvent(1, "AMD", "Advanced Micro Devices", "entry", "2026-09-25")
    def evaluate(body):
        return evaluate_candidate(event, ArticleEvidence("123", "2026-09-25", "Stock Buy", body, None, None, None, True))
    misleading = ('Other businesses are discussed [here](<https://issuer.example/AMD/stock-buy.pdf>).'
                  '\n\n![AMD stock buy](<https://images.example/AMD.png>)')
    assert "ticker_text_symbol" not in evaluate(misleading).evidence_codes
    assert evaluate(misleading).auto_eligible is False
    for link in ('<https://issuer.example/AMD/>', '[https://issuer.example/AMD/](<https://issuer.example/AMD/>)'):
        assert "ticker_text_symbol" not in evaluate(f'Other businesses are discussed at {link}.').evidence_codes
    assert "ticker_text_symbol" in evaluate('We initiated a position in [AMD](<https://issuer.example/report>) shares.').evidence_codes


def test_normal_native_dal_path_preserves_capture_observations(captured, scope_case, monkeypatch):
    path, backend = captured
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(path))
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(scope_case[1]))
    from src.sa_native_host import _handle_save_article_content
    from src.tools.data_access import DataAccessLayer

    dal = DataAccessLayer(base_path=path.parent, backend=backend)
    result = _handle_save_article_content(dal, {"article_id": "123", "body_markdown": "Operating income grew.",
                                              "body_capture": manifest(), "comments": []})
    assert result["status"] == "ok" and result["body_saved"] is True
    assert result["body_references"] == read_article(path, "123")["coverage"]["references"]


def test_v6_migration_preserves_text_and_does_not_invent_resource_evidence(captured):
    path, backend = captured
    body = "Historical prose without a resource manifest."
    with closing(store.connect(str(path))) as conn:
        conn.execute("UPDATE sa_articles SET body_markdown=?", (body,))
        conn.execute("ALTER TABLE sa_articles DROP COLUMN body_capture_json")
        conn.execute("DELETE FROM schema_migrations WHERE version=7")
        conn.execute("PRAGMA user_version=6")
        conn.commit()
    # A legacy local read does not install the new schema.
    assert read_article(path, "123")["coverage"]["references"]["status"] == "not_recorded"
    with closing(store.connect(str(path), read_only=True)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 6
    with closing(store.connect(str(path))) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 7
        assert tuple(conn.execute("SELECT body_markdown,body_capture_json FROM sa_articles").fetchone()) == (body, None)


def test_concurrent_v6_writers_install_the_nullable_column_once(captured):
    path, _ = captured
    with closing(store.connect(str(path))) as conn:
        conn.execute("ALTER TABLE sa_articles DROP COLUMN body_capture_json")
        conn.execute("DELETE FROM schema_migrations WHERE version=7")
        conn.execute("PRAGMA user_version=6")
        conn.commit()
    barrier = threading.Barrier(2)
    def migrate(_):
        barrier.wait(timeout=5)
        with closing(store.connect(str(path))) as conn:
            assert conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=7").fetchone()[0] == 1
            return conn.execute("PRAGMA user_version").fetchone()[0]
    with ThreadPoolExecutor(max_workers=2) as workers:
        assert list(workers.map(migrate, range(2))) == [7, 7]


@pytest.mark.parametrize("browser_name", ["chromium", "firefox"])
@pytest.mark.skipif(os.environ.get("ARKSCOPE_BROWSER_ACCEPTANCE") != "1", reason="isolated installed-browser gate")
def test_real_browser_preserves_selected_image_without_extra_requests_or_dom_changes(browser_name):
    from playwright.sync_api import sync_playwright

    url = "https://seekingalpha.com/alpha-picks/articles/123-fixture"
    html = '<!doctype html><h1>Provider article</h1>' + page(
        '<p>Original <a href="/report?q=one&amp;year=2026">Source Link</a>.</p>'
        '<figure><picture><source srcset="https://images.example/responsive.png 1x, https://images.example/large.png 2x">'
        '<img src="https://images.example/fallback.png" alt="Financial chart"></picture>'
        '<figcaption>Author caption</figcaption></figure>'
        '<img loading="lazy" style="margin-top:10000px" data-src="https://images.example/lazy.png" alt="Lazy chart">'
    ) + COMMENTS
    with sync_playwright() as pw:
        browser = getattr(pw, browser_name).launch(headless=True, proxy={"server": "http://127.0.0.1:9"})
        try:
            tab = browser.new_page()
            requests = []
            def respond(route):
                requests.append(route.request.url)
                if route.request.url == url:
                    route.fulfill(body=html, content_type="text/html")
                else:
                    route.abort()
            tab.route("**/*", respond)
            tab.goto(url)
            tab.wait_for_load_state("networkidle")
            before = tab.content(), tab.url, tab.evaluate("scrollY"), list(requests)
            current = tab.locator("picture img").evaluate("node=>node.currentSrc")
            assert current == "https://images.example/responsive.png"
            tab.evaluate((EXTENSION / "article_identity.js").read_text())
            result = tab.evaluate((EXTENSION / "scrape_detail.js").read_text())
            assert "error" not in result
            assert "![Financial chart](<" + current + ">)" in result["body_markdown"]
            assert "![Lazy chart](<https://images.example/lazy.png>)" in result["body_markdown"]
            assert "[Source Link](<https://seekingalpha.com/report?q=one&year=2026>)" in result["body_markdown"]
            assert "Reader reply" not in result["body_markdown"]
            assert result["body_capture"]["images"] == {"observed": 2, "retained": 2}
            assert (tab.content(), tab.url, tab.evaluate("scrollY"), requests) == before
        finally:
            browser.close()

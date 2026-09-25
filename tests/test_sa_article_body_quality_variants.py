"""Known capture variants must not become article prose or entry evidence."""

from contextlib import closing
import sqlite3

import pytest

from src import sa_capture_store as store
from src.sa.article_body_quality import assess_body, usable_body
from src.sa_article_reconciliation import PickEvent, evaluate_candidate
from src.sa_article_reconciliation_store import _article_evidence
from src.tools.backends.sa_capture_backend import SACaptureBackend


TITLE = "Investment update"
PROSE = "Margins improved as freight costs fell, despite weaker demand."
ANALYST = (
    "I/we have no stock, option or similar derivative position in any of the "
    "companies mentioned, and no plans to initiate any such positions within "
    "the next 72 hours. I wrote this article myself, and it expresses my own opinions."
)
SA = (
    "Past performance is no guarantee of future results. No recommendation or "
    "advice is being given as to whether any investment is suitable for a "
    "particular investor. Any views or opinions expressed above may not reflect "
    "those of Seeking Alpha as a whole."
)
ANALYST_EXTENDED = (
    ANALYST + " I am not receiving compensation for it (other than from Seeking "
    "Alpha). I have no business relationship with any company whose stock is "
    "mentioned in this article."
)
ANALYST_STAFF = (
    "I wrote this article myself, and it expresses my own opinions. "
    "I am not receiving compensation for it. I have no business relationship "
    "with any company whose stock is mentioned in this article."
)
SA_EXTENDED = (
    SA + " Seeking Alpha is not a licensed securities dealer, broker or US "
    "investment adviser or investment bank. Our analysts are third party authors "
    "that include both professional investors and individual investors who may "
    "not be licensed or certified by any institute or regulatory body."
)
SPLIT_DISCLOSURES = (
    "### Analyst's Disclosure\n\n" + ANALYST
    + "\n\n### Seeking Alpha's Disclosure\n\n" + SA
)
COMMENTS = (
    "# Investment update\n\n### Comments\n\nSort replies\n\n"
    "Reader: Stock Buy: ABC"
)


@pytest.mark.parametrize("body", [
    pytest.param(SPLIT_DISCLOSURES, id="separate-headings"),
    pytest.param(SPLIT_DISCLOSURES.replace("'", "\u2019"), id="curly-apostrophes"),
    pytest.param(ANALYST + "\n\n" + SA, id="unlabeled-paragraphs"),
    pytest.param(ANALYST, id="analyst-only"),
    pytest.param(SA, id="provider-only"),
    pytest.param(ANALYST_EXTENDED, id="analyst-with-compensation"),
    pytest.param(ANALYST_STAFF, id="staff-author-disclosure"),
    pytest.param(SA_EXTENDED, id="provider-with-licensing"),
    pytest.param(SA.replace(". ", ".\n\n"), id="separate-boilerplate-sentences"),
    pytest.param(ANALYST.replace(" ", " \n "), id="wrapped-boilerplate"),
    pytest.param("### Analyst's Disclosure", id="analyst-heading-only"),
    pytest.param("**Seeking Alpha's Disclosure**", id="provider-label-only"),
])
def test_observed_disclosure_variants_are_unusable(body):
    quality = assess_body(body, title=TITLE)
    assert quality["status"] == "unusable"
    assert quality["reason_code"] == "sa_article_body_disclosure_only"
    assert quality["completeness"] == "not_verified"
    assert usable_body(body, title=TITLE) == ""


@pytest.mark.parametrize("control", ["Sort replies", "SORT REPLIES", "Sort replies\nNewest"])
def test_unnumbered_comments_with_reply_sort_controls_are_unusable(control):
    body = COMMENTS.replace("Sort replies", control)
    quality = assess_body(body, title=TITLE)
    assert quality["status"] == "unusable"
    assert quality["reason_code"] == "sa_article_body_comment_thread"
    assert usable_body(body, title=TITLE) == ""


@pytest.mark.parametrize("template,reason", [
    ("{title}", "sa_article_body_metadata_only"),
    ("# {title}", "sa_article_body_metadata_only"),
    ("# {title}\n\n### Comments\n\nSort replies\n\nReader: ABC", "sa_article_body_comment_thread"),
])
def test_curly_apostrophe_titles_do_not_supply_narrative(template, reason):
    title = "Company\u2019s earnings"
    result = assess_body(template.format(title=title), title=title)
    assert result["status"] == "unusable"
    assert result["reason_code"] == reason


@pytest.mark.parametrize("body", [
    pytest.param(PROSE, id="short-prose"),
    pytest.param(SPLIT_DISCLOSURES + "\n\n" + PROSE, id="prose-after-disclosures"),
    pytest.param(PROSE + "\n\n" + SPLIT_DISCLOSURES, id="prose-before-disclosures"),
    pytest.param("### Analyst's Disclosure\n\n" + PROSE, id="heading-before-prose"),
    pytest.param(ANALYST + " " + PROSE, id="prose-in-analyst-paragraph"),
    pytest.param(ANALYST_STAFF + " " + PROSE, id="prose-after-staff-disclosure"),
    pytest.param(SA + " " + PROSE, id="prose-in-provider-paragraph"),
    pytest.param("I wrote this article myself, and it expresses my own opinions. " + PROSE,
                 id="prose-after-authorship"),
    pytest.param("Past performance is no guarantee of future results. " + PROSE,
                 id="caution-before-prose"),
    pytest.param("## Disclosure risks\n\nThe company omitted a material customer concentration disclosure.",
                 id="disclosure-analysis"),
    pytest.param("The Analyst's Disclosure: label identifies potential conflicts.",
                 id="label-in-prose"),
    pytest.param("## Comments\n\n" + PROSE, id="comments-section-prose"),
    pytest.param("## Comments\n\nSort replies by their discussion of operating margins.",
                 id="sort-words-in-sentence"),
    pytest.param(PROSE + "\n\n" + COMMENTS, id="prose-before-comment-thread"),
    pytest.param("| Year | Revenue |\n| --- | --- |\n| 2026 | 123 |", id="table"),
])
def test_genuine_short_and_mixed_prose_is_preserved_without_certifying_completeness(body):
    quality = assess_body(body, title=TITLE)
    assert quality["status"] == "available"
    assert quality["reason_code"] is None
    assert quality["completeness"] == "not_verified"
    assert usable_body(body, title=TITLE) == body


@pytest.fixture
def backend(tmp_path):
    backend = SACaptureBackend(sa_db=str(tmp_path / "sa.db"), market_db=":memory:")
    backend.upsert_sa_articles_meta([{
        "article_id": "123", "title": TITLE, "ticker": "ABC",
        "url": "https://seekingalpha.com/alpha-picks/articles/123-investment-update",
        "published_date": "2026-09-01", "article_type": "analysis",
    }])
    return backend


@pytest.mark.parametrize("body", [SPLIT_DISCLOSURES, ANALYST + "\n\n" + SA, COMMENTS],
                         ids=["split-disclosures", "unlabeled-disclosures", "comments-sort-replies"])
def test_bad_variant_recapture_preserves_good_body_and_time_but_keeps_comments(backend, body):
    old_time = "2020-01-01T00:00:00+00:00"
    with closing(store.connect(backend._sa_db)) as conn:
        conn.execute("UPDATE sa_articles SET body_markdown=?, detail_fetched_at=?", (PROSE, old_time))
        conn.commit()
    result = backend.save_article_with_comments("123", body, [{
        "comment_id": "c1", "commenter": "Reader", "comment_text": "Independent observation.",
        "comment_date": "2026-09-24T00:00:00Z", "upvotes": 0,
    }])
    with closing(sqlite3.connect(backend._sa_db)) as conn:
        assert conn.execute("SELECT body_markdown, detail_fetched_at FROM sa_articles").fetchone() == (PROSE, old_time)
        assert conn.execute("SELECT comment_text FROM sa_article_comments").fetchone()[0] == "Independent observation."
    assert result["body_saved"] is False


def test_comment_variant_cannot_supply_entry_role_evidence(backend):
    with closing(store.connect(backend._sa_db)) as conn:
        conn.execute("UPDATE sa_articles SET body_markdown=?, list_ticker='ABC'", (COMMENTS,))
        evidence = _article_evidence(conn.execute("SELECT * FROM sa_articles").fetchone())
    result = evaluate_candidate(PickEvent(1, "ABC", "ABC Inc.", "entry", "2026-09-01"), evidence)
    assert evidence.has_content is False
    assert evidence.body_markdown == ""
    assert result.auto_eligible is False
    assert "role_entry_strong" not in result.evidence_codes

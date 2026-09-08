import importlib.util
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("original_preview_diagnostic", Path(__file__).with_name("inspect_original.py"))
reader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reader)


def test_original_link_must_be_public_and_match_both_filing_identity_components():
    preview = "https://capedge.com/filing/123/0000000123-26-000456/OLD-8K"
    good = "https://www.sec.gov/Archives/edgar/data/123/000000012326000456/notice.htm"
    wrong_issuer = good.replace("/123/", "/999/")
    wrong_filing = good.replace("000456", "000789")
    body = ''.join(f'<a href="{url}">View original</a>' for url in (
        good, good + "#section", wrong_issuer, wrong_filing,
        good.replace("www.sec.gov", "www.sec.gov.invalid"),
        good.replace("https://", "http://"), good + "?credential=never", "http://127.0.0.1/"))
    assert reader.public_original_links(body.encode(), preview) == [good]


def test_absent_public_original_is_not_constructed_from_a_filename_guess():
    assert reader.public_original_links(b'<p>Log in to read more</p>',
        "https://capedge.com/filing/123/0000000123-26-000456/OLD-8K") == []

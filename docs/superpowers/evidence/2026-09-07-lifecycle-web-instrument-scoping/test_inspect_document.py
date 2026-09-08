import importlib.util
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("primary_filing_diagnostic", Path(__file__).with_name("inspect_document.py"))
reader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reader)


def test_primary_document_uses_the_typed_row_and_observed_inline_viewer_link():
    base = "https://www.sec.gov/Archives/edgar/data/123/456/456-index.htm"
    def row(url, kind):
        return f'<tr><td>1</td><td>Document</td><td><a href="{url}">body.htm</a></td><td>{kind}</td><td>500</td></tr>'
    body = '<table>' + row('/ixviewer/doc/action?doc=/Archives/edgar/data/123/456/body.htm', '8-K')
    body += row('exhibit.htm', 'EX-3.1') + row('https://www.sec.gov/Archives/edgar/data/999/456/foreign.htm', '8-K') + '</table>'
    assert reader.primary_documents(body.encode(), base) == ["https://www.sec.gov/Archives/edgar/data/123/456/body.htm"]


def test_index_with_no_typed_primary_row_does_not_invent_a_document_url():
    assert reader.primary_documents(b'<a href="example.htm">8-K</a>',
        "https://www.sec.gov/Archives/edgar/data/123/456/456-index.htm") == []

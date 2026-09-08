"""Follow the observed filing index's typed 8-K row, not a guessed filename."""

import argparse
from dataclasses import asdict
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
from urllib.parse import urljoin, urlsplit
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.with_name("2026-09-07-lifecycle-web-usage-canary")))
import claude_canary as original


def primary_documents(body, index_url):
    class Rows(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.rows, self.row, self.cell, self.hrefs = [], None, None, []

        def handle_starttag(self, tag, attrs):
            if tag == "tr":
                self.row, self.hrefs = [], []
            elif tag == "td" and self.row is not None:
                self.cell = []
            elif tag == "a" and self.cell is not None and dict(attrs).get("href"):
                self.hrefs.append(dict(attrs)["href"])

        def handle_data(self, data):
            if self.cell is not None:
                self.cell.append(data)

        def handle_endtag(self, tag):
            if tag == "td" and self.cell is not None:
                self.row.append(''.join(self.cell).strip())
                self.cell = None
            elif tag == "tr" and self.row is not None:
                self.rows.append((self.row, self.hrefs))
                self.row = self.cell = None

    parser = Rows()
    parser.feed(body.decode("utf-8", errors="strict"))
    parser.close()
    directory = urlsplit(index_url).path.rsplit('/', 1)[0] + '/'
    links = set()
    for cells, hrefs in parser.rows:
        if len(cells) != 5 or cells[3] != "8-K":
            continue
        for href in hrefs:
            value = urlsplit(urljoin(index_url, href))
            if value.path.startswith("/ixviewer/") or value.path == "/ix":
                from urllib.parse import parse_qs
                query = parse_qs(value.query, strict_parsing=True)
                if set(query) != {"doc"} or len(query["doc"]) != 1:
                    continue
                value = urlsplit(urljoin(index_url, query["doc"][0]))
            if (value.scheme == "https" and value.hostname == "www.sec.gov" and value.path.startswith(directory)
                    and not value.query and value.username is None and value.password is None
                    and value.port in (None, 443) and value.path.endswith((".htm", ".html"))):
                links.add(value._replace(fragment="").geturl())
    return sorted(links)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--seal", required=True)
    args = parser.parse_args()
    source = original.require_sources(ROOT, HERE / "admission", args.seal)
    prior = Path("/tmp/lifecycle-instrument-original-r1")
    metrics = json.loads((prior / "metrics.json").read_text())
    assert metrics["source_http_campaign_used"] == 7 and metrics["source_http_campaign_remaining"] == 17
    assert metrics["status"] == "captured_public_original" and len(metrics["original_links"]) == 1
    index_url = metrics["original_links"][0]
    assert index_url.endswith("-index.htm")
    work = args.work.resolve()
    assert not work.exists() and work.is_relative_to(Path("/tmp"))
    work.mkdir(mode=0o700)
    from src import lifecycle_public_sources as sources
    from src.lifecycle_web_sec_sources import SecSourcePolicy
    reader = sources.PublicSourceReader(sources.SourceReadLimits(17, 2, 32 * 1024**2, 180, 128 * 1024**2),
        sec_policy=SecSourcePolicy(user_agent=original.sec_contact(args.profile) or ""))
    observed = {"purpose": "Inspect the publicly linked 8-K body after the prior original link resolved only to filing metadata",
        "source_checkpoint": source, "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "prior_receipt_sha256": hashlib.sha256((prior / "metrics.json").read_bytes()).hexdigest(),
        "sdk_submissions": 0, "prior_source_http_attempts": 7, "source_http_limit": 24,
        "document_links": [], "reads": [], "no_login_or_paywall_bypass": True, "production_writes": False}
    original.write_new_json(work / "prepared.json", observed)
    convert = sources._page_text

    def observe_index(body, content_type, **kwargs):
        result = convert(body, content_type, **kwargs)
        observed["document_links"] = primary_documents(body, index_url)
        return result

    def read(url, filename):
        page = reader.read(url)
        observed["reads"].append({"url": page.url, "body_sha256": page.body_sha256, "text_sha256": page.text_sha256,
            "capture_sha256": page.capture_sha256, "text_characters": len(page.text)})
        original.write_new_json(work / filename, asdict(page))
        return page

    try:
        with patch.object(sources, "_page_text", observe_index):
            read(index_url, "index-page.json")
        if len(observed["document_links"]) != 1:
            raise ValueError("public_primary_document_ambiguous")
        read(observed["document_links"][0], "document-page.json")
        observed["status"] = "captured_primary_document"
    except (sources.SourceReadError, ValueError) as exc:
        observed.update(status="unresolved", code=str(exc))
    finally:
        reader.request_stop()
        observed["source_http_attempts"] = reader.request_count
        observed["observations"] = [asdict(value) for value in reader.observations]
        observed["source_http_campaign_used"] = 7 + reader.request_count
        observed["source_http_campaign_remaining"] = 17 - reader.request_count
        original.write_new_json(work / "metrics.json", observed)
    print(json.dumps(observed, indent=2))


if __name__ == "__main__":
    main()

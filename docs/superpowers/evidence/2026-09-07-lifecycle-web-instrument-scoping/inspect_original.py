"""Bounded diagnostic: follow a public preview's explicit original-filing link."""

import argparse
from dataclasses import asdict
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import urljoin, urlsplit
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.with_name("2026-09-07-lifecycle-web-usage-canary")))
import claude_canary as original


def public_original_links(body, preview_url):
    match = re.fullmatch(r"/filing/([0-9]+)/([0-9]{10}-[0-9]{2}-[0-9]{6})/[^/]+", urlsplit(preview_url).path)
    if match is None:
        raise ValueError("original_filing_identity_unavailable")
    directory = f"/Archives/edgar/data/{int(match[1])}/{match[2].replace('-', '')}/"

    class Links(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.urls = set()

        def handle_starttag(self, tag, attrs):
            if tag != "a":
                return
            href = dict(attrs).get("href")
            if not href:
                return
            value = urlsplit(urljoin(preview_url, href))
            if (value.scheme == "https" and value.hostname == "www.sec.gov" and value.path.startswith(directory)
                    and value.username is None and value.password is None and value.port in (None, 443)
                    and not value.query and value.path.lower().endswith((".htm", ".html"))):
                self.urls.add(value._replace(fragment="").geturl())

    parser = Links()
    parser.feed(body.decode("utf-8", errors="strict"))
    parser.close()
    return sorted(parser.urls)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--seal", required=True)
    args = parser.parse_args()
    source = original.require_sources(ROOT, HERE / "admission", args.seal)
    run = HERE / "live-r1"
    assert hashlib.sha256((run / "files.sha256.json").read_bytes()).hexdigest() == "bcdb7581d9447177ad386e7c85d2b4eea73b6c1d59a472d590ff86504d7a5ab1"
    receipt = json.loads((run / "verification.json").read_text())
    assert receipt["source_http_attempts"] == 5 and receipt["source_http_budget_remaining"] == 19
    search = json.loads((run / "search-output.json").read_text())
    previews = [url for url in search["sources"] if urlsplit(url).hostname == "capedge.com"]
    if len(previews) != 1:
        raise ValueError("preview_selection_ambiguous")
    work = args.work.resolve()
    assert not work.exists() and work.is_relative_to(Path("/tmp"))
    work.mkdir(mode=0o700)
    from src import lifecycle_public_sources as sources
    from src.lifecycle_web_sec_sources import SecSourcePolicy
    limits = sources.SourceReadLimits(max_requests=19, max_redirects=2,
        max_response_bytes=32 * 1024**2, max_decoded_bytes=128 * 1024**2, timeout_seconds=180)
    reader = sources.PublicSourceReader(limits, sec_policy=SecSourcePolicy(user_agent=original.sec_contact(args.profile) or ""))
    observed = {"purpose": "Check whether the selected public preview omitted decisive sections available at its explicitly linked public original",
        "source_checkpoint": source, "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "sdk_submissions": 0, "prior_source_http_attempts": 5, "source_http_limit": 24,
        "original_links": [], "reads": [], "no_login_or_paywall_bypass": True, "production_writes": False}
    original.write_new_json(work / "prepared.json", observed)
    convert = sources._page_text

    def observe_original(body, content_type, **kwargs):
        result = convert(body, content_type, **kwargs)
        observed["original_links"] = public_original_links(body, previews[0])
        observed["preview_body_sha256"] = hashlib.sha256(body).hexdigest()
        return result

    def read(url, filename):
        page = reader.read(url)
        observed["reads"].append({"url": page.url, "body_sha256": page.body_sha256, "text_sha256": page.text_sha256,
            "capture_sha256": page.capture_sha256, "text_characters": len(page.text)})
        original.write_new_json(work / filename, asdict(page))
        return page

    try:
        with patch.object(sources, "_page_text", observe_original):
            read(previews[0], "preview.json")
        if len(observed["original_links"]) != 1:
            raise ValueError("public_original_link_ambiguous")
        read(observed["original_links"][0], "original-page.json")
        observed["status"] = "captured_public_original"
    except (sources.SourceReadError, ValueError) as exc:
        observed.update(status="unresolved", code=str(exc))
    finally:
        reader.request_stop()
        observed["source_http_attempts"] = reader.request_count
        observed["observations"] = [asdict(value) for value in reader.observations]
        observed["source_http_campaign_used"] = 5 + reader.request_count
        observed["source_http_campaign_remaining"] = 19 - reader.request_count
        original.write_new_json(work / "metrics.json", observed)
    print(json.dumps(observed, indent=2))


if __name__ == "__main__":
    main()

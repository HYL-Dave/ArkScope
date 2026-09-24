"""Generate an isolated Firefox harness from actual production capture functions.

Run with python -m tests.sa_comment_acceptance.build OUTPUT_DIRECTORY.
This test utility installs nothing and never contacts a provider or native host.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys

from tests.test_sa_extension_reconciliation_flow import ROOT, _run_background


def build(output: Path):
    source = ROOT / "extensions/sa_alpha_picks"
    harness = Path(__file__).parent
    payload = _run_background("""
      return {profiles:COMMENT_SCROLL_PROFILES,settle:ARTICLE_INITIAL_SETTLE_MS,
        functions:[beginArticleCapture,captureArticle,scrollToComments,getCommentScrollProfile,
          settleArticleBeforeScroll,injectDetailScraper,injectCommentsScraper,readSaAccessMarkers]
          .map(f=>f.toString())};
    """)
    files = ["comment_capture.js", "article_identity.js", "scrape_detail.js", "scrape_comments.js", "compat_firefox.js"]
    hashes = {name:hashlib.sha256((source / name).read_bytes()).hexdigest() for name in ["background.js", *files]}
    source_hash = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    for name in files:
        shutil.copyfile(source / name, output / name)
    for name in ("test_background.js", "panel.html", "panel.js", "panel.css"):
        shutil.copyfile(harness / name, output / name)
    (output / "capture_driver.js").write_text(
        "const COMMENT_SCROLL_PROFILES=" + json.dumps(payload["profiles"]) + ";\n"
        + "const ARTICLE_INITIAL_SETTLE_MS=" + str(payload["settle"]) + ";\n"
        + "const CAPTURE_SOURCE_HASH=" + json.dumps(source_hash) + ";\n"
        + "function sleep(ms){return new Promise(resolve=>setTimeout(resolve,ms));}\n"
        + "\n\n".join(payload["functions"]) + "\n", encoding="utf-8")
    manifest = {
        "manifest_version":3,"name":"ArkScope Comment Test","version":"1.0.2",
        "permissions":["scripting","tabs","storage","downloads"],
        "host_permissions":["https://seekingalpha.com/*"],
        "background":{"scripts":["compat_firefox.js","comment_capture.js","capture_driver.js","test_background.js"]},
        "action":{"default_title":"ArkScope Comment Test"},
        "browser_specific_settings":{"gecko":{"id":"sa-comment-test@arkscope.local","strict_min_version":"121.0"}},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output / "source_hashes.json").write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")
    return source_hash


if __name__ == "__main__":
    print(build(Path(sys.argv[1]).expanduser().resolve()))

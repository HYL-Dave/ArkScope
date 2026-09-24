"""The live acceptance package has no production service or automated navigation."""
import json
import os
import subprocess
from pathlib import Path
import tempfile

import pytest


def test_acceptance_package_is_isolated_and_uses_production_capture(tmp_path):
    from tests.sa_comment_acceptance.build import build
    from tests.test_sa_extension_reconciliation_flow import ROOT, _run_background

    output = tmp_path / "extension"
    build(output)
    manifest = json.loads((output / "manifest.json").read_text())
    assert "nativeMessaging" not in manifest["permissions"]
    assert "alarms" not in manifest["permissions"]
    assert manifest["browser_specific_settings"]["gecko"]["id"] == "sa-comment-test@arkscope.local"
    driver = (output / "capture_driver.js").read_text()
    functions = _run_background("return [captureArticle,beginArticleCapture,scrollToComments].map(f=>f.toString());")
    assert all(function in driver for function in functions)
    assert "sendNativeMessage" not in driver
    for name in ("comment_capture.js", "scrape_detail.js", "scrape_comments.js", "article_identity.js"):
        assert (output / name).read_bytes() == (ROOT / "extensions/sa_alpha_picks" / name).read_bytes()
    assert not any(Path(output).rglob("*.db"))


def test_capture_comparison_does_not_hide_missing_comments_with_equal_counts():
    from tests.sa_comment_acceptance.compare import compare
    base = dict(article_id="123",mode="manual",status="captured",detail={"body_markdown":"body"},
                source_hash="same",document_key="doc1",provider_count=2,
                scroll={"rounds":4,"elapsed_ms":4000},strategy="observe")
    comment = dict(comment_id="1",commenter="a",comment_date="2026-01-01",comment_text="body",parent_comment_id=None)
    old = dict(base,comments=[comment])
    new = dict(base,strategy="guarded",document_key="doc2",comments=[dict(comment,comment_id="2",comment_text="other")])
    assert compare(old,new)["status"] == "not_accepted"
    new["comments"] = [comment]
    assert compare(old,new)["status"] == "no_regression_observed"
    new["document_key"] = "doc1"
    assert compare(old,new)["status"] == "inconclusive"


def test_positive_provider_count_with_two_empty_captures_is_not_evidence():
    from tests.sa_comment_acceptance.compare import compare
    common = dict(article_id="123",mode="manual",status="captured",detail={"body_markdown":"body"},
                  source_hash="same",provider_count=3,comments=[],scroll={"rounds":2,"elapsed_ms":2000})
    assert compare(dict(common,strategy="observe",document_key="one"),
                   dict(common,strategy="guarded",document_key="two"))["status"] == "inconclusive"


def test_each_acceptance_panel_keeps_its_own_article():
    script = r"""
    const fs=require('node:fs'),vm=require('node:vm');
    let action,message,next=301;const reads=[];
    const chrome={action:{onClicked:{addListener:f=>action=f}},
      runtime:{id:'test',getURL:p=>'moz-extension://test/'+p,onMessage:{addListener:f=>message=f}},
      tabs:{create:async()=>({id:next++}),update:async()=>{},get:async id=>{reads.push(id);return {url:'https://seekingalpha.com/article/123-test',status:'complete'};}},
      storage:{local:{get:async()=>({}),set:async()=>{}}},
      scripting:{executeScript:async()=>[{result:'human_verification_required'}]}};
    vm.runInNewContext(fs.readFileSync('tests/sa_comment_acceptance/test_background.js','utf8'),
      {chrome,URL,Date,readSaAccessMarkers:()=>{},CAPTURE_SOURCE_HASH:'test'});
    (async()=>{
      await action({id:101,url:'https://seekingalpha.com/article/123-test'});
      await action({id:102,url:'https://seekingalpha.com/article/456-other'});
      await new Promise(resolve=>message({action:'capture',strategy:'observe'},{id:'test',tab:{id:301}},resolve));
      process.stdout.write(JSON.stringify(reads));
    })().catch(e=>{console.error(e);process.exitCode=1});
    """
    result = subprocess.run(["node","-e",script],text=True,capture_output=True,check=True)
    assert json.loads(result.stdout) == [101]


@pytest.mark.skipif(os.environ.get("ARKSCOPE_BROWSER_ACCEPTANCE") != "1", reason="installed Firefox package gate")
def test_installed_firefox_acceptance_panel_and_driver(tmp_path):
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service
    from tests.sa_comment_acceptance.build import build

    package = tmp_path / "extension"
    fingerprint = build(package)
    # Test hooks are added only to this offline copy, never the operator package.
    with (package / "test_background.js").open("a") as hooks:
        hooks.write("""
        chrome.runtime.onMessage.addListener((m,s,respond)=>{
          if(m.action!=='offline_probe') return false;
          respond({driver:typeof captureArticle,guard:typeof SACommentCapture.documentState,
            native_permission:chrome.runtime.getManifest().permissions.includes('nativeMessaging')});
          return false;
        });
        """)
    options = Options()
    options.binary_location = "/snap/firefox/current/usr/lib/firefox/firefox"
    options.add_argument("-headless")
    options.set_preference("network.proxy.type", 1)
    for scheme in ("http", "ssl"):
        options.set_preference("network.proxy." + scheme, "127.0.0.1")
        options.set_preference("network.proxy." + scheme + "_port", 9)
    with tempfile.TemporaryDirectory(prefix="arkscope-comment-offline-", dir=Path.home()/"snap/firefox/common") as profiles:
        driver = webdriver.Firefox(options=options, service=Service(executable_path="/snap/bin/geckodriver",
            service_args=["--profile-root", profiles, "--allow-system-access"], log_output=str(tmp_path/"firefox.log")))
        try:
            addon = driver.install_addon(str(package), temporary=True)
            driver.set_context("chrome")
            identity = driver.execute_script('return JSON.parse(Services.prefs.getStringPref("extensions.webextensions.uuids"))[arguments[0]]',addon)
            driver.set_context("content")
            driver.get(f"moz-extension://{identity}/panel.html")
            driver.set_script_timeout(15)
            probe = driver.execute_async_script("const done=arguments[arguments.length-1];browser.runtime.sendMessage({action:'offline_probe'}).then(done)")
            assert probe == {"driver":"function","guard":"function","native_permission":False}
            assert driver.find_element("id","revision").text == fingerprint
            driver.find_element("id","capture").click()
            from selenium.webdriver.support.ui import WebDriverWait
            WebDriverWait(driver,10).until(lambda d:not d.find_element("id","capture").get_property("disabled"))
            assert "No selected article" in driver.find_element("id","status").text
            for width in (900, 450):
                driver.set_window_size(width, 800)
                assert driver.execute_script("return document.documentElement.scrollWidth <= innerWidth")
                driver.save_screenshot(str(tmp_path/f"panel-{width}.png"))
        finally:
            driver.quit()

"use strict";
let running = false;
const selections = new Map();

chrome.action.onClicked.addListener(async tab => {
  if (running) return;
  const panel = await chrome.tabs.create({active:false});
  selections.set(panel.id,{tabId:tab.id,url:tab.url,status:"Ready"});
  await chrome.tabs.update(panel.id,{url:chrome.runtime.getURL("panel.html"),active:true});
});

async function captureTest(strategy, selection) {
  if (!selection) return {error:"No selected article; open the test from its toolbar icon on an article"};
  if (running) return {error:"Capture already running"};
  if (!["observe","guarded"].includes(strategy)) return {error:"Invalid strategy"};
  running = true;
  try {
    const tabId = selection.tabId;
    const tab = await chrome.tabs.get(tabId);
    const url = new URL(tab.url);
    if (tab.url.split('#')[0] !== selection.url.split('#')[0]) return {error:"Selected article changed; select it again"};
    const match = url.pathname.match(/^\/(?:alpha-picks\/articles|article)\/(\d+)(?:-[^/]*)?\/?$/);
    if (url.origin !== "https://seekingalpha.com" || !match || tab.status !== "complete") {
      return {error:"Select a loaded SA article with the extension toolbar button"};
    }
    const stored = await chrome.storage.local.get("attempts");
    const attempts = stored.attempts || [];
    if (attempts.length >= 6) return {error:"Six-run test limit reached"};
    if (attempts.length && Date.now() - attempts.at(-1).at < 60000) return {error:"Wait at least 60 seconds between attempts"};
    const access = await chrome.scripting.executeScript({target:{tabId},func:readSaAccessMarkers});
    if (!access[0] || access[0].result) return {error:access[0]?.result || "Page access could not be checked"};
    const start = await chrome.scripting.executeScript({target:{tabId},func:() => {
      const heading = Array.from(document.querySelectorAll('h2,h3,h4,[role="heading"],button,a')).map(el => el.textContent.trim())
        .find(text => /^comments\s*\([\d,]+\)$/i.test(text));
      return {document_key:location.origin + ':' + performance.timeOrigin,
        provider_count:heading ? Number(heading.match(/[\d,]+/)[0].replaceAll(',','')) : null};
    }});
    const initial = start[0]?.result;
    if (!initial) return {error:"Missing document evidence"};
    if (attempts.some(item=>item.document_key === initial.document_key)) return {error:"Reload the article before a new run"};
    attempts.push({at:Date.now(),document_key:initial.document_key,article_id:match[1],strategy});
    await chrome.storage.local.set({attempts});
    selection.status = "Capturing " + match[1] + " / " + strategy;
    await chrome.tabs.update(tabId,{active:true});
    let result;
    try {
      const captured = await captureArticle(tabId,{article_id:match[1],url:tab.url},"manual",true,{strategy,trace:true});
      result = {...captured,status:captured.detail && !captured.detail.error ? "captured" : "capture_failed"};
    } catch (error) {
      result = {status:"capture_failed",reason:error.code || "capture_exception",trace:error.capture_trace || null};
    }
    const lastResult = {...result,...initial,article_id:match[1],mode:"manual",strategy,
      source_hash:CAPTURE_SOURCE_HASH,captured_at:new Date().toISOString(),schema_version:1};
    const blob = URL.createObjectURL(new Blob([JSON.stringify(lastResult,null,2)],{type:"application/json"}));
    try {
      await chrome.downloads.download({url:blob,filename:"ArkScope-Comment-Test/" + match[1] + "-" + strategy + "-" + Date.now() + ".json",saveAs:false});
    } finally {setTimeout(()=>URL.revokeObjectURL(blob),60000);}
    selection.status = lastResult.status + " / " + (lastResult.comments?.length ?? 0) + " comments / " + (lastResult.reason || "JSON exported");
    return {status:selection.status};
  } catch (_) {
    return {error:"Test failed; no automatic retry"};
  } finally {running = false;}
}

chrome.runtime.onMessage.addListener((message,sender,respond) => {
  if (sender.id !== chrome.runtime.id) return false;
  const selection = selections.get(sender.tab?.id);
  if (message.action === "status") {
    respond({running,status:selection?.status || "No selected article",target:selection?.url || "",
      source_hash:CAPTURE_SOURCE_HASH}); return false;
  }
  if (message.action === "capture") {
    captureTest(message.strategy,selection).then(result=>{
      if (selection && result.error) selection.status = result.error;
      respond(result);
    }); return true;
  }
  return false;
});

"use strict";
let running = false;
const selections = new Map();

chrome.action.onClicked.addListener(async tab => {
  if (running) return;
  const panel = await chrome.tabs.create({active:false});
  selections.set(panel.id,{tabId:tab.id,url:tab.url,status:"Ready"});
  await chrome.tabs.update(panel.id,{url:chrome.runtime.getURL("panel.html"),active:true});
});

// Passive diagnostic only: no clicks, scrolling, DOM writes or provider calls.
function inspectLoadedComments(articleId) {
  const match = location.pathname.match(/^\/(?:alpha-picks\/articles|article)\/(\d+)(?:-[^/]*)?\/?$/);
  if (location.origin !== "https://seekingalpha.com" || !match || match[1] !== articleId) {
    return {error:"Selected article changed"};
  }
  const rowSelector = '[class*="border-t-share-separator-thin"]';
  const rows = Array.from(document.querySelectorAll(rowSelector));
  const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]'))
    .filter(el=>/^comments(?:\s*\([\d,]+\))?$/i.test(el.textContent.trim()));
  function describe(el) {
    return {tag:el.tagName.toLowerCase(),role:el.getAttribute('role'),
      classes:Array.from(el.classList).slice(0,10).map(name=>name.slice(0,80)),
      comment_rows:rows.filter(row=>el.contains(row)).length};
  }
  function ancestry(el) {
    const ancestors = [];
    let parent = el.parentElement;
    for (; parent && ancestors.length < 16; parent = parent.parentElement) {
      ancestors.push({...describe(parent),
        comment_headings:headings.filter(heading=>parent.contains(heading)).slice(0,4).map(heading=>heading.textContent.trim().slice(0,100)),
        children:Array.from(parent.children).slice(0,8).map(child=>({...describe(child),contains_target:child.contains(el)})),
        child_count:parent.children.length});
      if (parent.matches('body')) {parent=null; break;}
    }
    return {ancestors,ancestors_truncated:!!parent};
  }
  const controls = Array.from(document.querySelectorAll('button,a,[role="button"]'))
    .map(el=>({el,label:el.textContent.trim().replace(/\s+/g,' ')}))
    .filter(item=>/^(?:show|see|read|view|load)\b.*\b(?:more|comments?|replies|reply)\b/i.test(item.label));
  return {article_id:articleId,document_key:location.origin+':'+performance.timeOrigin,
    comment_rows:rows.length,control_count:controls.length,omitted_controls:Math.max(0,controls.length-64),
    controls:controls.slice(0,64).map(({el,label})=>{
      const link=el.closest('a[href]'),button=el.closest('button,input');
      let href=null;
      if(link) {
        try {const url=new URL(link.href);href=/^https?:$/.test(url.protocol)?url.origin+url.pathname:url.protocol;}
        catch(_){href='invalid';}
      }
      const knownLabel = /^(?:show|see|read|view|load)\s+(?:(?:all|more|previous|older|\d+)\s+)*(?:comments?|replies|reply)(?:\s*\([\d,]+\))?$/i.test(label)
        || /^(?:show|see|read)\s+(?:more|less)(?:\s*\.{3})?$/i.test(label);
      return {...describe(el),label:knownLabel ? label.slice(0,100) : null,href,
        button_type:button?.type || null,form_associated:!!button?.form,...ancestry(el)};
    }),
    row_samples:rows.slice(0,3).map(el=>({...describe(el),...ancestry(el)}))};
}

async function exportTestArtifact(result, articleId, suffix) {
  const blob = URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:"application/json"}));
  try {
    await chrome.downloads.download({url:blob,filename:"ArkScope-Comment-Test/" + articleId + "-" + suffix + "-" + Date.now() + ".json",saveAs:false});
  } finally {setTimeout(()=>URL.revokeObjectURL(blob),60000);}
}

async function inspectTest(selection) {
  if (!selection) return {error:"No selected article; open the test from its toolbar icon on an article"};
  if (running) return {error:"Capture already running"};
  running = true;
  try {
    const tab = await chrome.tabs.get(selection.tabId);
    const url = new URL(tab.url);
    const match = url.pathname.match(/^\/(?:alpha-picks\/articles|article)\/(\d+)(?:-[^/]*)?\/?$/);
    if (url.origin !== "https://seekingalpha.com" || !match || tab.status !== "complete"
        || tab.url.split('#')[0] !== selection.url.split('#')[0]) return {error:"Selected article changed or not loaded"};
    const probe = await chrome.scripting.executeScript({target:{tabId:selection.tabId},
      func:inspectLoadedComments,args:[match[1]]});
    const result = probe[0]?.result;
    if (!result || result.error) return {error:result?.error || "Structure could not be read"};
    await exportTestArtifact({...result,kind:"loaded_comment_structure",schema_version:1,
      source_hash:CAPTURE_SOURCE_HASH,inspected_at:new Date().toISOString()},match[1],"structure");
    selection.status = "Loaded comment structure exported";
    return {status:selection.status};
  } catch (_) {
    return {error:"Structure export failed; no automatic retry"};
  } finally {running = false;}
}

async function captureTest(strategy, selection, mode) {
  if (!selection) return {error:"No selected article; open the test from its toolbar icon on an article"};
  if (running) return {error:"Capture already running"};
  if (!["observe","guarded"].includes(strategy)) return {error:"Invalid strategy"};
  mode = mode || "backfill";
  if (!["backfill","quick"].includes(mode)) return {error:"Invalid capture profile"};
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
    selection.status = "Capturing " + match[1] + " / " + strategy + " / " + mode;
    await chrome.tabs.update(tabId,{active:true});
    let result;
    try {
      const captured = await captureArticle(tabId,{article_id:match[1],url:tab.url},mode,true,{strategy,trace:true});
      result = {...captured,status:captured.detail && !captured.detail.error ? "captured" : "capture_failed"};
    } catch (error) {
      result = {status:"capture_failed",reason:error.code || "capture_exception",trace:error.capture_trace || null};
    }
    const lastResult = {...result,...initial,article_id:match[1],mode,strategy,
      capture_profile:getCommentScrollProfile(mode),
      source_hash:CAPTURE_SOURCE_HASH,captured_at:new Date().toISOString(),schema_version:2};
    await exportTestArtifact(lastResult,match[1],strategy);
    selection.status = lastResult.status + " / " + (lastResult.comments?.length ?? 0) + " comments / "
      + (lastResult.reason || lastResult.scroll?.stop_reason || "JSON exported");
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
  if (message.action === "capture" || message.action === "inspect") {
    const task = message.action === "capture" ? captureTest(message.strategy,selection,message.mode) : inspectTest(selection);
    task.then(result=>{
      if (selection && result.error) selection.status = result.error;
      respond(result);
    }); return true;
  }
  return false;
});

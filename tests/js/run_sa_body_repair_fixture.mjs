import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';
import {JSDOM} from 'jsdom';

const dir = path.resolve('extensions/sa_alpha_picks');
const scenario = process.argv[2];
const key = 'saArticleBodyRecoveryV2';
const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const tick = () => new Promise(resolve => setImmediate(resolve));
const targets = Array.from({length: 8}, (_, index) => ({
  article_id: String(1000 + index), url: `https://seekingalpha.com/alpha-picks/articles/${1000 + index}-example`,
  title: `Article ${index + 1}`, published_date: '2026-09-24', body_sha256: 'a'.repeat(64),
  priority: index, reasons: ['body_missing'],
}));
const manifest = {status:'ok',protocol_version:2,manifest_id:'a'.repeat(64),as_of:'2026-09-25',
  targets,counts:{targets:8},settings:{max_articles_per_job:0,body_lookback_days:0,body_scope:'all_retained',comment_scope:'current'}};
const bodyCapture = {schema_version:1, extractor_version:2,
  links:{observed:2,retained:2}, images:{observed:1,retained:1}, unsupported_embeds:0};
const bodyReferences = {status:'observed_references_retained',basis:'selected_article_dom',
  extractor_version:2, image_storage:'remote_references_only',
  links:{observed:2,retained:2}, images:{observed:1,retained:1}, unsupported_embeds:0};

function event() {
  const listeners = new Set();
  return {addListener: listener => listeners.add(listener), removeListener: listener => listeners.delete(listener),
    emit: (...args) => [...listeners].forEach(listener => listener(...args))};
}

function storage(initial = {}) {
  const data = clone(initial), changed = event();
  return {data, changed, local: {
    get(keys, callback) {
      const out = keys == null ? clone(data) : Object.fromEntries((Array.isArray(keys) ? keys : [keys])
        .map(name => [name, clone(data[name])]));
      if (callback) queueMicrotask(() => callback(out));
      return Promise.resolve(out);
    },
    async set(values) {
      const changes = {};
      for (const [name, value] of Object.entries(values)) {
        changes[name] = {oldValue: clone(data[name]), newValue: clone(value)};
        data[name] = clone(value);
      }
      changed.emit(changes, 'local');
    },
  }};
}

async function until(predicate) {
  for (let i = 0; i < 500; i++) {
    if (predicate()) return;
    await new Promise(resolve => setTimeout(resolve,1));
  }
  assert.fail('expected observable transition did not occur');
}

function background(options = {}) {
  const store = storage({alphaPicksAutoSyncEnabled: true, marketNewsAutoSyncEnabled: true,
    ...options.initial});
  const native = [], events = [], tabs = new Map(), sent = [], alarms = [], ports = [];
  let listener, batchDeadline, nextTab = 1, now = Date.parse('2026-09-25T00:00:00Z');
  let job=null, admitted=null, turn=null;
  const receipts=new Map(), storedBodies=new Set();
  const collectorIdentity={client_id:'f'.repeat(32),browser:'chrome'};
  store.data.companyCollectorIdentity=collectorIdentity;
  class Clock extends Date {
    constructor(...args) {super(...(args.length ? args : [now]));}
    static now() {return now;}
  }
  const shared = {status: 'ok', policy: {hour_limit: 100, day_limit: 1000, hour_reserve: 10, day_reserve: 100},
    ledger_id: 'ledger', generation: 1, is_owner: !options.otherOwner,owner:collectorIdentity,
    paused_reason: options.paused || null, capability_pauses: {}, rate_limited: false,
    financial_gap_seconds:60, next_navigation_at:options.initialPacing ? new Clock(now + 60000).toISOString() : null};
  function summary() {
    if(!job)return {status:'ok',protocol_version:2,state:'not_started'};
    const counts={selected:job.items.length,saved:0,failed:0,skipped:0,pending:0};
    for(const item of job.items)counts[['running','pending'].includes(item.state)?'pending':item.state]++;
    if(!counts.pending)job.state=job.state==='cancelling'||job.state==='cancelled'?'cancelled':counts.failed?'partial':'complete';
    return {status:'ok',protocol_version:2,job_id:job.job_id,revision:job.revision,state:job.state,
      manifest_id:manifest.manifest_id,counts,settings:manifest.settings,reason_code:job.reason_code||null,next_eligible_at:null};
  }
  function bodyControl(message) {
    if(!shared.is_owner)return {status:'error',error_code:'sa_body_owner_changed'};
    if(message.operation==='start')job={job_id:'e'.repeat(32),revision:1,state:'pending',items:clone(targets).map(t=>({...t,state:'pending'}))};
    if(!job)return summary();
    if(message.operation==='cancel') {
      if(!['cancelling','cancelled'].includes(job.state))job.revision++;
      job.state=admitted?'cancelling':'cancelled';
      job.items.filter(i=>i.state==='pending').forEach(i=>{i.state='skipped';i.reason_code='operator_cancelled';});
    }
    if(message.operation==='items')return {...summary(),items:clone(job.items),next_cursor:null};
    if(message.operation==='next'&&!['complete','partial','paused','cancelling','cancelled'].includes(summary().state)) {
      if(admitted){job.state='running';return summary();}
      if(shared.paused_reason){job.state='paused';return {...summary(),reason_code:shared.paused_reason};}
      if(Date.parse(shared.next_navigation_at)>now||options.capacity||options.pacing) {
        job.state='waiting';events.push('gap_wait');
        return {...summary(),reason_code:options.capacity?'capacity_exhausted':'site_pacing',next_eligible_at:shared.next_navigation_at};
      }
      job.state='pending';return {...summary(),target:clone(job.items.find(i=>i.state==='pending'))};
    }
    return summary();
  }
  const chrome = {
    runtime: {
      id: 'test-extension', getURL: name => `chrome-extension://test-extension/${name}`,
      getManifest: () => ({version: 'test'}), lastError: null,
      onMessage: {addListener: fn => { listener = fn; }}, onInstalled: event(), onStartup: event(),
      sendMessage: async value => { sent.push(clone(value)); },
      connectNative() {
        const port = {onMessage:event(),onDisconnect:event(),closed:false,
          postMessage(message) {
            assert.deepEqual(clone(message),{action:'ping'});
            if (options.handshakeTimeout || options.holdHandshake) return;
            queueMicrotask(() => options.lifetimeUnavailable ? port.onDisconnect.emit() : port.onMessage.emit({status:'ok'}));
          },
          disconnect() {this.closed=true;events.push('lifetime_close');},
        };
        ports.push(port); events.push('lifetime_open'); return port;
      },
      sendNativeMessage(_host, message, callback) {
        native.push(clone(message));
        Promise.resolve().then(async () => {
          if (options.native) {
            const value = await options.native(message);
            if (value !== undefined) return value;
          }
          if (message.action === 'preview_article_body_recovery') return clone(options.manifest || manifest);
          if (message.action === 'article_body_recovery_control') return bodyControl(message);
          if (message.action === 'check_article_body_recovery_target') {
            return {status: 'ok', target: clone(targets.find(item => item.article_id === message.article_id))};
          }
          if (message.action === 'save_article_body_recovery') {
            events.push(`save:${message.article_id}`);
            storedBodies.add(message.article_id);
            return {status: 'ok', body_saved: true, body_quality: {state: 'usable'}, body_references:bodyReferences};
          }
          if (message.action === 'record_extension_job') return {status: 'ok', persisted: true, run_id:native.length};
          if (message.action === 'sa_acquisition_control') {
            events.push(message.operation);
            if(message.operation==='reconcile_task')return {...shared,pending_task:{...message,state:admitted?'active':'terminal'}};
            if (message.operation === 'begin_task' && options.pacingRace) {
              options.pacingRace = false;
              shared.next_navigation_at = new Clock(now + 60000).toISOString();
              return {status:'deferred',reason:'site_pacing',retry_after:shared.next_navigation_at};
            }
            if (message.operation === 'begin_task' && message.task_operation === 'alpha_picks_body_repair'
                && (Date.parse(shared.next_navigation_at) > now || options.pacing)) {
              return {status:'deferred',reason:'site_pacing',error_code:'sa_company_pacing',retry_after:shared.next_navigation_at};
            }
            if (message.operation === 'begin_task') {
              if(options.capacity)return {status:'deferred',reason:'capacity_exhausted'};
              admitted=message;const item=job?.items.find(i=>i.article_id===message.article_id);
              if(item)item.state='running';
              return {...shared,token:'b'.repeat(32),task_id:'c'.repeat(32)};
            }
            if (message.operation === 'admit_navigation') return options.navDenied || job?.state==='cancelling'
              ? {status: 'deferred', reason: 'capacity_exhausted'}
              : {...shared, allowed: true, replayed: false, attempt_id: 'd'.repeat(32)};
            if (message.operation === 'observe_restriction') shared.paused_reason = message.reason;
            if (message.operation === 'finish_task') {
              assert.equal(tabs.size, 0, 'gate cannot release while the active tab is open');
              shared.next_navigation_at = new Clock(now + 60000).toISOString();
              const item=job?.items.find(i=>i.article_id===admitted?.article_id);
              if(item) {
                item.state=storedBodies.has(item.article_id)?'saved':job.state==='cancelling'?'skipped'
                  :shared.paused_reason||message.result.status==='deferred'?'pending'
                  :message.result.status==='cancelled'?'skipped':'failed';
                item.reason_code=message.result.error_code||null;
              }
              const receipt={task_id:'c'.repeat(32),body_recovery_job_id:admitted?.body_job_id,article_id:admitted?.article_id};
              receipts.set(receipt.task_id,receipt);admitted=null;
              return {...shared,acquisition:receipt};
            }
            return clone(shared);
          }
          assert.fail(`unexpected native action ${message.action}`);
        }).then(value => callback(clone(value))).catch(error => { console.error(error); process.exitCode = 1; callback({status:'error'}); });
      },
    },
    storage: {local: store.local, onChanged: store.changed},
    alarms: {onAlarm: event(), create: async (...args) => alarms.push(args), clear: async name => {
      for(let i=alarms.length-1;i>=0;i--)if(alarms[i][0]===name)alarms.splice(i,1);return true;
    }},
    tabs: {
      onUpdated: event(), onRemoved: event(), onCreated: event(),
      async create(value) {
        events.push('create');
        assert.equal(value.active,true,'body repair must activate its admitted article tab for lazy content');
        const id = nextTab++;
        const dom = new JSDOM('<h1>Article</h1><article>' + 'Article content. '.repeat(80) + '</article>',
          {url:value.url, runScripts:'outside-only'});
        Object.defineProperty(dom.window.HTMLElement.prototype, 'innerText', {get() {return this.textContent;}});
        dom.window.scrollTo = () => {events.push('settle');};
        dom.window.scrollBy = () => assert.fail('body repair must not traverse comments');
        tabs.set(id, {id, url:value.url, status:'complete', dom});
        return {id, url:value.url, status:'complete'};
      },
      get(id, callback) {
        const tab = tabs.get(id);
        const value = tab && {id, url:tab.url, status:'complete'};
        if (callback) queueMicrotask(() => callback(value));
        return Promise.resolve(value);
      },
      async remove(id) {
        events.push('close');
        if (options.closeFails) throw new Error('fixture cleanup failed');
        tabs.get(id)?.dom.window.close();
        tabs.delete(id);
        chrome.tabs.onRemoved.emit(id);
      },
      async update(id, value) {
        Object.assign(tabs.get(id), value);
        return {id, ...value};
      },
    },
    scripting: {async executeScript({target, files, func, args = []}) {
      const tab = tabs.get(target.tabId);
      assert.ok(tab, 'only an owned open tab may be scraped');
      if (files) {
        assert.deepEqual(clone(files), ['article_identity.js', 'scrape_detail.js']);
        events.push('detail');
        if (options.detail) await options.detail(chrome, tab);
        return [{result:{title:'Article title', body_markdown:'PRIVATE BODY CONTENT', url:tab.url,
          body_capture:bodyCapture,
          detail_ticker:'ABC', detail_ticker_observed_at:'2026-09-25T00:00:00Z'}}];
      }
      if (func.name === 'readSaAccessMarkers' && options.restriction) return [{result:options.restriction}];
      if (func.name === 'documentState') events.push(`guard:${args[0].phase}`);
      const pageFunction = tab.dom.window.eval(`(${func.toString()})`);
      return [{result:await pageFunction(...args)}];
    }},
  };
  const context = vm.createContext({chrome, console:{log() {}, warn() {}}, URL, TextEncoder, crypto:webcrypto, Date:Clock,
    navigator:{userAgent:'Test Chrome'}, setTimeout(fn, delay) {
      if (delay === 30 * 60 * 1000) batchDeadline = fn;
      if (delay === 15000 && options.handshakeTimeout) return setTimeout(fn,0);
      if (delay === 60000 || delay === 20000) {
        events.push('gap_wait');
        if (options.idleGap) assert.ok(ports.every(port=>port.closed),'no lifetime port may cover idle waits');
        if (options.disconnectGap) {
          options.disconnectGap=false;
          queueMicrotask(()=>ports[0].onDisconnect.emit());
          return setTimeout(fn,60000);
        }
        if (options.expireGap) {
          options.expireGap=false;
          queueMicrotask(()=>batchDeadline());
          return setTimeout(fn,60000);
        }
        if (options.holdGap) return setTimeout(fn, 60000);
        return setTimeout(() => {now += delay; fn();}, 0);
      }
      return setTimeout(fn,delay);
    }, clearTimeout});
  context.importScripts = (...names) => names.forEach(name =>
    vm.runInContext(fs.readFileSync(path.join(dir, name), 'utf8'), context, {filename:name}));
  context.importScripts('background.js');
  context.sleep = async () => {};
  const sender = {id:chrome.runtime.id, url:chrome.runtime.getURL('popup.html')};
  const message = (value, from = sender) => new Promise(resolve => {
    const asyncReply = listener(value, from, resolve);
    if (!asyncReply) resolve({status:'unhandled'});
  });
  const terminal = async () => {
    for(let i=0;i<25;i++) {
      if(turn)await turn;
      const state=await context.articleBodyRecovery.status();
      if(['complete','partial','cancelled','paused'].includes(state.state)||state.status==='error'||store.data.saAcquisitionPending)return state;
      if(options.capacity||options.pacing||options.navDenied||options.lifetimeUnavailable||options.handshakeTimeout)return state;
      now=Math.max(now,Date.parse(state.next_eligible_at)||0,Date.parse(shared.next_navigation_at)||0);
      if(options.expireGap)now+=31*60000;
      if(options.idleGap)assert.ok(ports.every(p=>p.closed),'idle work holds no lifetime');
      turn=context.articleBodyRecovery.wake();
    }
    assert.fail('job did not become terminal');
  };
  const wake=()=>{turn=context.articleBodyRecovery.wake();return turn;};
  return {context,chrome,store,native,events,tabs,sent,alarms,ports,message,terminal,wake,
    summary,hasBatchTimeout:()=>!!batchDeadline,advance:ms=>{now+=ms;}};
}

async function start(app) {
  const preview = await app.message({action:'preview_article_body_recovery'});
  assert.equal(preview.status, 'ok', 'readonly preview must be supported');
  const result = await app.message({action:'start_article_body_recovery', manifest_id:preview.manifest_id,
    targets:[...targets].reverse(), limit:100});
  assert.equal(result.status, 'ok', 'explicit start should be accepted');
  app.wake();
  return result;
}

function actions(app, action) {return app.native.filter(value => value.action === action);}

async function runBackground() {
  if (scenario === 'preview_bound') {
    const app = background();
    const rejected = await app.message({action:'preview_article_body_recovery'}, {id:'other',url:'https://example.com'});
    assert.equal(rejected.status, 'error');
    assert.equal(app.native.length, 0);
    const preview = await app.message({action:'preview_article_body_recovery',as_of:'1990-01-01'});
    assert.equal(preview.status, 'ok', 'readonly preview must be supported');
    assert.equal(preview.targets.length, 8);
    assert.equal(preview.counts.targets, 8);
    assert.deepEqual(app.native, [{action:'preview_article_body_recovery',protocol_version:2}]);
    assert.equal(app.tabs.size, 0);
    assert.notEqual((await app.message({action:'start_article_body_recovery',manifest_id:'stale'})).status, 'ok');
    assert.equal(app.alarms.length, 0);
    return;
  }
  const options = {};
  let app, release, held, routine;
  if (scenario === 'owner_gate') options.otherOwner = true;
  if (scenario === 'pause_gate') options.paused = 'login_required';
  if (scenario === 'capacity_gate') options.capacity = true;
  if (scenario === 'navigation_gate') options.navDenied = true;
  if (scenario === 'site_stop') options.restriction = 'human_verification_required';
  if (scenario === 'cleanup_failed') options.closeFails = true;
  if (scenario === 'cancel_gap') options.holdGap = true;
  if (scenario === 'idle_gap') options.idleGap = true;
  if (scenario === 'pacing_stop') options.pacing = true;
  if (scenario === 'initial_pacing') options.initialPacing = true;
  if (scenario === 'pacing_race') options.pacingRace = true;
  if (scenario === 'lifetime_disconnect') options.disconnectGap = true;
  if (scenario === 'lifetime_unavailable') options.lifetimeUnavailable = true;
  if (scenario === 'lifetime_handshake_timeout') options.handshakeTimeout = true;
  if (scenario === 'lifetime_deadline') options.expireGap = true;
  if (scenario === 'lifetime_cancel_setup') options.holdHandshake = true;
  if (['lifetime_disconnect','lifetime_disconnect_active'].includes(scenario)) {
    let disconnected=false;
    options.detail=async()=>{if(!disconnected){disconnected=true;app.ports.find(p=>!p.closed).onDisconnect.emit();}};
  }
  if (scenario === 'interrupted') options.initial = {saArticleBodyRecovery: {status:'running',batch_id:'lost',items:[
    {article_id:'1000',title:'Article 1',state:'running',attempt_count:1},
    {article_id:'1001',title:'Article 2',state:'queued',attempt_count:0},
  ]}};
  if (['priority', 'cancel_active'].includes(scenario)) {
    held = new Promise(resolve => {release = resolve;});
    let calls = 0;
    options.detail = async () => {if (++calls === 1) await held;};
  }
  if (scenario === 'navigation_changed') options.detail = async (chrome, tab) => {
    chrome.tabs.onUpdated.emit(tab.id, {status:'loading'});
  };
  if (scenario === 'revalidate') options.native = message => {
    if (message.action === 'check_article_body_recovery_target') return {
      status:'skipped', reason:['already_present','out_of_scope','source_changed'][Number(message.article_id) % 3],
    };
  };
  if (scenario === 'save_rejected') options.native = message => {
    if (message.action === 'save_article_body_recovery') return {
      status:'ok', ok:true, body_saved:false, error:'PRIVATE RAW FAILURE', body_quality:{reason:'too_short'},
    };
  };
  if (scenario === 'save_comment_thread') options.native = message => {
    if (message.action === 'save_article_body_recovery') return {
      status:'error',body_saved:false,error_code:'sa_article_body_comment_thread',
      body_quality:{status:'unusable',reason_code:'sa_article_body_comment_thread'},
    };
  };
  app = background(options);
  if (scenario === 'interrupted') {
    const state = await app.message({action:'get_article_body_recovery_state'});
    assert.equal(state.state,'not_started');
    assert.equal(state.legacy_history.batch_id,'lost');
    assert.equal(app.store.data[key],undefined);
    assert.equal(app.ports.length,0);
    return;
  }
  if(scenario==='owner_gate') {
    const result=await app.message({action:'start_article_body_recovery',manifest_id:manifest.manifest_id});
    assert.equal(result.status,'error');assert.equal(app.tabs.size,0);assert.equal(app.ports.length,0);return;
  }
  if (scenario === 'cancel_queued' || scenario === 'lane_priority') {
    held = new Promise(resolve => {release = resolve;});
    routine = app.context.enqueueSaSyncJob({key:'blocking-routine'}, async () => held);
    await tick();
  }
  const started = await start(app);
  if (scenario === 'lifetime_cancel_setup') {
    await until(()=>app.ports.length===1);
    await app.message({action:'cancel_article_body_recovery',job_id:started.job_id});
  }
  if (scenario === 'lane_priority') {
    const preferred = app.context.enqueueSaSyncJob({key:'newer-routine'}, async () => {app.events.push('routine');return {};});
    release();
    await preferred;
  }
  if (scenario === 'cancel_gap' || scenario === 'gap_priority') {
    await app.wake();
    assert.ok(app.events.includes('gap_wait'));
    assert.equal(app.store.data.saAcquisitionPending,null,'gap wait holds no gate');
    if (scenario === 'cancel_gap') {
      await app.message({action:'cancel_article_body_recovery',job_id:started.job_id});
    } else {
      await app.context.enqueueSaSyncJob({key:'routine-during-gap'}, async () => {
        app.events.push('routine'); return {};
      });
    }
  }
  if (['priority', 'cancel_active'].includes(scenario)) await until(() => app.events.includes('detail'));
  if (scenario === 'priority') {
    routine = app.context.enqueueSaSyncJob({key:'routine'}, async () => {app.events.push('routine'); return {};});
    release();
  }
  if (['cancel_active','cancel_queued'].includes(scenario)) {
    const cancelled = await app.message({action:'cancel_article_body_recovery',job_id:started.job_id});
    assert.equal(cancelled.status, 'ok');
    release();
  }
  const batch = await app.terminal();
  await tick();
  assert.ok(app.ports.every(port=>port.closed),'native lifetime ends with each page, never spans an idle wait');
  assert.equal(app.hasBatchTimeout(),false,'no whole-job lifetime deadline');
  if (routine) await routine;
  const saves = actions(app, 'save_article_body_recovery');
  const checks = actions(app, 'check_article_body_recovery_target');
  const telemetry = actions(app, 'record_extension_job');
  assert.equal(app.store.data.alphaPicksAutoSyncEnabled, true);
  assert.equal(app.store.data.marketNewsAutoSyncEnabled, true);
  assert.ok(!JSON.stringify(telemetry).includes('PRIVATE'), 'telemetry cannot contain body or native prose');
  assert.ok(!JSON.stringify(app.store.data[key]).includes('PRIVATE'), 'local result is metadata only');
  assert.ok(app.native.every(value => !['save_article_content','save_comments_only','accept_reconciliation_link'].includes(value.action)));
  if (['repair_success','priority','gap_priority','lane_priority','idle_gap','initial_pacing','pacing_race','lifetime_deadline'].includes(scenario)) {
    assert.equal(saves.length, 8);
    assert.equal(checks.length, 8);
    assert.deepEqual(saves.map(value => value.article_id),targets.map(t=>t.article_id));
    assert.equal(batch.state, 'complete');
    assert.equal(batch.counts.saved, 8);
    assert.equal(app.alarms.length,0);
    assert.equal(app.ports.length,scenario==='pacing_race'?9:8);
    for (const save of saves) assert.deepEqual(Object.keys(save).sort(), [
      'action','article_id','expected_body_sha256','body_markdown','body_capture','detail_ticker','detail_ticker_observed_at',
      'protocol_version','client','token','generation','task_id','body_job_id',
    ].sort());
    for (const save of saves) assert.deepEqual(save.body_capture,bodyCapture);
    for (const save of saves)assert.equal(save.body_job_id,started.job_id);
    assert.ok(saves.every(value => value.expected_body_sha256 === 'a'.repeat(64)));
    assert.equal(app.events.filter(value => value === 'guard:end').length, 8);
    assert.equal(app.events.filter(value => value === 'finish_task').length, 8);
    assert.ok(telemetry.every(value => value.result.healthy_anchor_eligible === false));
    assert.equal(telemetry.length, scenario === 'pacing_race' ? 9 : 8);
    if (scenario === 'pacing_race') assert.equal(telemetry[0].result.derived_outcome,'deferred');
    assert.ok(app.events.filter(value => value === 'gap_wait').length >= 4);
    assert.ok(app.events.indexOf('guard:begin') < app.events.indexOf('settle'));
    assert.ok(app.events.indexOf('guard:end') < app.events.indexOf('close'));
    assert.ok(app.events.indexOf('close') < app.events.indexOf('finish_task'));
    if (scenario === 'priority' || scenario === 'gap_priority') {
      assert.ok(app.events.indexOf('routine') < app.events.indexOf('save:1001'));
      assert.ok(app.events.indexOf('routine') > app.events.indexOf('save:1000'));
    }
    if (scenario === 'lane_priority') assert.ok(app.events.indexOf('routine') < app.events.indexOf('create'));
    if (scenario === 'initial_pacing') assert.ok(app.events.indexOf('gap_wait') < app.events.indexOf('create'));
    if (scenario === 'pacing_race') assert.equal(app.events.filter(value=>value==='create').length,8);
    assert.notEqual((await app.message({action:'start_article_body_recovery',manifest_id:'invalid'})).status,'ok');
  } else if (scenario === 'cancel_gap') {
    assert.equal(batch.state,'cancelled');
    assert.equal(saves.length,1);
    assert.equal(app.tabs.size,0);
  } else if (['cancel_active','cancel_queued','lifetime_cancel_setup'].includes(scenario)) {
    assert.equal(batch.state, 'cancelled');
    assert.equal(saves.length, 0);
    assert.equal(app.tabs.size, 0);
    assert.equal(app.events.filter(value => value === 'create').length, scenario === 'cancel_active' ? 1 : 0);
  } else if (['pause_gate','capacity_gate','navigation_gate','pacing_stop'].includes(scenario)) {
    assert.ok(['waiting','paused'].includes(batch.state));
    assert.equal(saves.length, 0);
    assert.equal(app.tabs.size, 0);
    assert.equal(batch.counts.pending,8);
  } else if (scenario === 'site_stop') {
    assert.equal(batch.state, 'paused');
    assert.equal(app.events.filter(value => value === 'create').length, 1);
    assert.equal(saves.length, 0);
    assert.equal(batch.counts.pending,8);
    assert.equal(app.tabs.size, 0);
  } else if (scenario === 'revalidate') {
    assert.equal(checks.length, 8);
    assert.equal(batch.counts.skipped, 8);
    assert.equal(batch.counts.saved, 0);
    assert.equal(saves.length, 0);
    assert.equal(app.events.filter(value => value === 'create').length, 0);
  } else if (['lifetime_disconnect','lifetime_unavailable','lifetime_handshake_timeout','lifetime_disconnect_active'].includes(scenario)) {
    assert.equal(saves.length,['lifetime_disconnect','lifetime_disconnect_active'].includes(scenario)?7:0);
    assert.equal(app.tabs.size,0);
    if (scenario === 'lifetime_disconnect_active') {
      assert.equal(telemetry.length,8);
      assert.equal(telemetry[0].result.derived_outcome,'failed');
      assert.equal(telemetry[0].result.phases.extraction.reason_code,'native_host_unavailable');
      assert.equal(batch.counts.failed,1);
    }
  } else if (scenario === 'save_rejected' || scenario === 'save_comment_thread') {
    assert.equal(saves.length, 8);
    assert.equal(batch.counts.failed, 8);
    assert.equal(batch.counts.saved, 0);
    assert.equal(batch.state, 'partial');
    assert.ok(telemetry.every(value => value.result.derived_outcome === 'failed'));
    const reason = scenario === 'save_rejected' ? 'parser_empty' : 'sa_article_body_comment_thread';
    assert.ok(batch.items.every(item=>item.reason_code===reason));
    assert.ok(telemetry.every(value => value.extension_diagnostics.entries.some(entry =>
      entry.stage === 'content_parse' && entry.reason_code === reason)));
    assert.ok(telemetry.every(value=>value.result.phases.extraction.reason_code===reason));
    await app.message({action:'preview_article_body_recovery'});
    assert.equal((await app.context.articleBodyRecovery.status()).counts.failed,8,'preview retains native attempt results');
  } else if (scenario === 'navigation_changed') {
    assert.equal(saves.length, 0);
    assert.ok(telemetry.some(value=>value.extension_diagnostics.entries.some(entry=>entry.reason_code==='article_context_changed')));
    assert.equal(app.tabs.size, 0);
  } else if (scenario === 'cleanup_failed') {
    assert.equal(batch.state, 'running');
    assert.equal(saves.length, 1);
    assert.equal(app.events.filter(value => value === 'finish_task').length, 0);
    assert.ok(app.store.data.saAcquisitionPending);
  }
}

async function popup() {
  const dom = new JSDOM(fs.readFileSync(path.join(dir,'popup.html'),'utf8'), {runScripts:'outside-only'});
  const store = storage({alphaPicksAutoSyncEnabled:true,marketNewsAutoSyncEnabled:true});
  const sent = [];
  let startCallback;
  let popupState = {status:'ok',state:'not_started'};
  const reply = message => {
    if (message.action === 'get_article_body_recovery_state') return popupState;
    if (message.action === 'preview_article_body_recovery') return {...manifest,protocol_version:2,counts:{targets:8,held:0,excluded:0},settings:{max_articles_per_job:0}};
    if (message.action === 'get_company_refresh') return {status:'ok',config:{enabled:false,target_mode:'watchlist',tickers:[],statements:['income_statement'],views:['annual'],interval_days:7},collector:{status:'ok',generation:0,owner:null,policy:null},scopes:[],running:false};
    if (message.action === 'preview_company_refresh') return {status:'error'};
    return {status:'ok',events:[],total:0};
  };
  dom.window.chrome = {runtime:{lastError:null,onMessage:event(),sendMessage(message, callback) {
    sent.push(clone(message));
    if (message.action === 'start_article_body_recovery') {startCallback = callback; return;}
    if (callback) queueMicrotask(() => callback(reply(message)));
    return Promise.resolve(reply(message));
  }}, storage:{local:store.local,onChanged:store.changed}};
  for (const script of dom.window.document.querySelectorAll('script[src]')) {
    dom.window.eval(fs.readFileSync(path.join(dir,script.getAttribute('src')), 'utf8'));
  }
  await tick();
  const document = dom.window.document;
  const preview = document.getElementById('bodyRecoveryPreviewBtn');
  const start = document.getElementById('bodyRecoveryStartBtn');
  assert.ok(preview && start, 'body repair controls must exist');
  // Reopening an idle popup previews local targets, never starts capture.
  assert.equal(start.disabled,false);
  assert.match(start.textContent,/Start repair/i);
  assert.match(document.getElementById('bodyRecoveryPreview').textContent,/8 selected/);
  assert.equal(document.querySelectorAll('#bodyRecoveryTargets li').length,5);
  assert.ok(!document.getElementById('bodyRecoveryTargets').textContent.includes('Article 6'));
  assert.equal(sent.filter(value => value.action === 'start_article_body_recovery').length,0);
  start.click(); start.click();
  assert.equal(sent.filter(value => value.action === 'start_article_body_recovery').length,1);
  assert.equal(start.disabled,true);
  assert.deepEqual(sent.find(value => value.action === 'start_article_body_recovery'),
    {action:'start_article_body_recovery',manifest_id:manifest.manifest_id});
  startCallback({status:'ok',job_id:'job',state:'running',items:[],counts:{selected:8,saved:0,failed:0,skipped:0,pending:8}});
  await tick();
  popupState = {status:'ok',job_id:'job',state:'waiting',reason_code:'site_pacing',next_eligible_at:new Date(Date.now()+60000).toISOString(),items:[
    {article_id:'1000',title:'Article 1',state:'saved'},
    {article_id:'1001',title:'Article 2',state:'queued'},
  ],counts:{selected:8,saved:1,failed:0,skipped:0,pending:7}};
  await store.local.set({saArticleBodyRecoveryV2:{job_id:'job'}});
  await tick();
  assert.match(document.getElementById('bodyRecoveryTiming').textContent,/Waiting until.*site_pacing/);
  assert.equal(document.getElementById('bodyRecoveryProgress').value,1);
  assert.equal(document.getElementById('bodyRecoveryProgress').max,8);
  assert.equal(start.disabled,true);
  popupState = {status:'ok',job_id:'job',state:'partial',items:[
    {article_id:'1000',title:'Article 1',state:'failed',reason_code:'detail_save_failed'},
  ],counts:{selected:8,saved:7,failed:1,skipped:0,pending:0}};
  await store.local.set({saArticleBodyRecoveryV2:{job_id:'job'}});
  await tick();
  assert.match(document.getElementById('bodyRecoveryResult').textContent,/detail_save_failed/);
  assert.equal(document.getElementById('bodyRecoveryTiming').hidden,true);
  assert.equal(start.disabled,true, 'new preview is required after any attempt');
  assert.equal(document.getElementById('alphaPicksAutoSyncToggle').checked,true);
  assert.equal(document.getElementById('marketNewsAutoSyncToggle').checked,true);
  assert.ok(sent.every(value => !['set_alpha_picks_auto_sync','set_market_news_auto_sync'].includes(value.action)));
  dom.window.close();
}

async function combinedSaveRejected() {
  const app = background();
  const c = app.context;
  // Browser capture is covered above; isolate the two existing save consumers here.
  c.managedSaTabs.create = async () => ({id:99});
  c.managedSaTabs.update = async () => {};
  c.chrome.tabs.update = async () => {};
  c.waitForTabLoad = c.scrollToLoadAll = c.cleanupCollectorTabs = c.registerCollectorTab = c.unregisterCollectorTab = async () => {};
  c.safeRemoveTab = async () => true;
  c.waitForArticleReady = c.waitForArticlesReady = async () => ({ok:true});
  c.injectArticlesListScraper = async () => [targets[0]];
  c.captureArticle = async () => ({detail:{body_markdown:'body'},comments:[],scroll:{mode:'quick'}});
  const calls = [];
  c.sendNativeMessage2 = async message => {
    calls.push(message.action);
    if (message.action === 'save_articles_meta') return {status:'ok',need_content:[targets[0]]};
    if (message.action === 'save_article_content') return {status:'ok',ok:true,body_saved:false,
      comment_scan_usable:true,comment_backfill_pending:false,net_new_comments:2};
    return {status:'ok'};
  };
  const diagnostics = c.SAExtensionDiagnostics.createCollector();
  const details = await c.doDetailFetch(99,[], 'quick', diagnostics);
  assert.equal(details.fetched,0,'comment persistence is not body success');
  assert.equal(details.failed,1);
  assert.equal(details.net_new_comments,2,'saved comments retain their own truthful count');
  assert.equal(diagnostics.freeze().entries[0].reason_code,'parser_empty');
  const manual = await c.doManualFetch([{...targets[0],symbol:'ABC',role:'entry',lineage_id:1,
    event_anchor_date:'2026-09-24'}], c.SAExtensionDiagnostics.createCollector());
  assert.equal(manual.fetched,0);
  assert.equal(manual.failed,1);
  assert.equal(manual.accepted,0);
  assert.ok(!calls.includes('accept_reconciliation_link'));
}

if (scenario === 'popup') await popup();
else if (scenario === 'combined_save_rejected') await combinedSaveRejected();
else await runBackground();
process.stdout.write(`${scenario}: ok\n`);

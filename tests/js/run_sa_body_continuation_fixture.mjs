import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const scenario = process.argv[2];
const source = fs.readFileSync('extensions/sa_alpha_picks/article_body_recovery.js', 'utf8');
const key = 'saArticleBodyRecoveryV2';
const alarm = 'saArticleBodyRecoveryContinuation';
const data = {}, alarms = new Map(), events = [], saved = new Set();
let now = Date.parse('2026-09-28T00:00:00Z'), seq = 0, starts = 0, navigations = 0;
let job = null, pending = null, worker, hook = null, offline = false;
let deadline = 0, restricted = false, ownerChanged = false, loseStart = false, loseCheckpoint = false;
const owner = {client_id: 'f'.repeat(32), browser: 'firefox'};
const targets = Array.from({length:8}, (_,i) => ({article_id:String(1000+i), title:'Article '+i,
  url:`https://seekingalpha.com/alpha-picks/articles/${1000+i}-fixture`, body_sha256:'a'.repeat(64)}));
const manifest = {status:'ok',protocol_version:2,manifest_id:'b'.repeat(64),as_of:'2026-09-28',
  targets,counts:{targets:8},settings:{max_articles_per_job:0,body_lookback_days:0,body_scope:'all_retained',comment_scope:'current'}};
function summary() {
  const counts = {selected:8,saved:saved.size,failed:job.failed.size,skipped:job.skipped.size,
    pending:8-saved.size-job.failed.size-job.skipped.size};
  if (!counts.pending && !['cancelled','cancelling'].includes(job.state)) job.state = counts.failed ? 'partial' : 'complete';
  return {status:'ok',protocol_version:2,job_id:job.id,revision:job.revision,state:job.state,
    manifest_id:manifest.manifest_id,counts,settings:manifest.settings,reason_code:null,next_eligible_at:null};
}
async function control(operation, fields={}) {
  events.push(operation);
  if (offline) throw Error('disconnected');
  if (ownerChanged) return {status:'error',error_code:'sa_body_owner_changed'};
  if (operation === 'start') {
    starts++;
    if (!job) job = {id:'c'.repeat(32),revision:1,state:'pending',failed:new Set(),skipped:new Set(),request_id:fields.request_id};
    else assert.equal(fields.request_id,job.request_id);
    if (loseStart) {loseStart=false; throw Error('reply lost');}
  }
  if (!job) return {status:'ok',protocol_version:2,state:'not_started'};
  if (operation === 'cancel') {
    if (job.state !== 'cancelled') job.revision++;
    job.state='cancelled';
    targets.filter(t=>!saved.has(t.article_id)&&!job.failed.has(t.article_id)).forEach(t=>job.skipped.add(t.article_id));
  }
  if (operation === 'resume') {
    if (restricted || fields.confirm_handled !== true) return {status:'error',error_code:'sa_body_site_paused'};
    job.state='pending';
  }
  if (operation === 'checkpoint' && loseCheckpoint) {loseCheckpoint=false; throw Error('checkpoint reply lost');}
  if (operation === 'items') return {...summary(),items:targets.map(t=>({...t,state:saved.has(t.article_id)?'saved':'pending'})),next_cursor:null};
  if (operation === 'next' && !['complete','partial','cancelled','paused'].includes(job.state)) {
    if (hook) {const fn=hook;hook=null;await fn();}
    if (job.state==='cancelled') return summary();
    if (restricted) {job.state='paused';return {...summary(),reason_code:'login_required'};}
    if (now<deadline) {job.state='waiting';return {...summary(),next_eligible_at:new Date(deadline).toISOString(),reason_code:'site_pacing'};}
    const target=targets.find(t=>!saved.has(t.article_id)&&!job.failed.has(t.article_id)&&!job.skipped.has(t.article_id));
    if (target) {job.state='pending';return {...summary(),target};}
  }
  return summary();
}
function make() {
  const ctx={console,Date,URL,crypto:{randomUUID:()=>`request-${++seq}`}};
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync('extensions/sa_alpha_picks/acquisition_queue.js','utf8'),ctx);
  vm.runInContext(source,ctx);
  const queue=ctx.SAQueue.create({now:()=>now});
  return ctx.SAArticleBodyRecovery.create({
    storage:{get:async keys=>structuredClone(typeof keys==='string'?{[keys]:data[keys]}:data),
      set:async values=>Object.assign(data,structuredClone(values))},
    alarms:{create:async(name,value)=>alarms.set(name,value),clear:async name=>alarms.delete(name)},
    now:()=>now,uuid:()=>`request-${++seq}`,
    native:async message=>{assert.equal(message.protocol_version,2);return structuredClone(manifest);},control,
    collector:async()=>({status:'ok',is_owner:!ownerChanged,owner,generation:1,ledger_id:'d'.repeat(32)}),
    reconcilePending:async()=>({pending}),
    enqueue:(opts,callback)=>queue.enqueue({...opts,priority:'background',run:async()=>{
      assert.equal(opts.trigger,'continuation');assert.equal(opts.acquisition.body_job_id,job.id);
      assert.equal(opts.intent_revision,job.revision);
      if (opts.eligible && !await opts.eligible()) return {status:'cancelled'};
      events.push('admit');
      if (scenario==='cancel_admission') await worker.cancel(job.id);
      const result=await callback({});
      queue.enqueue({key:'financial-'+seq++,priority:'background',run:async()=>events.push('financial')});
      queue.enqueue({key:'news-'+seq++,priority:'routine',run:async()=>events.push('news')});
      return result;
    }}),
    capture:async(target,run)=>{
      if(run.cancelled)return {status:'cancelled'};
      navigations++;events.push('navigate:'+target.article_id);
      assert.ok(!saved.has(target.article_id),'never navigate a saved article');
      assert.ok(now>=deadline,'respect native pacing');
      if(scenario==='cancel_save') await worker.cancel(job.id);
      if(scenario==='partial'&&target.article_id==='1000') job.failed.add(target.article_id);
      else saved.add(target.article_id);
      now+=7*60*1000; deadline=now+60000;
      return {status:job.failed.has(target.article_id)?'error':'ok',body_saved:saved.has(target.article_id),
        acquisition:{task_id:target.article_id.padStart(32,'0'),body_recovery_job_id:job.id,article_id:target.article_id}};
    },
  });
}
worker=make();
async function start() {await worker.preview();return worker.start(manifest.manifest_id);}
async function turns(n=15) {
  for(let i=0;i<n&&alarms.has(alarm);i++) {
    now=Math.max(now,alarms.get(alarm).when);alarms.delete(alarm);
    const before=navigations;
    await worker.wake();
    assert.ok(navigations-before<=1,'one article per turn');
  }
}
if(scenario==='no_intent') {
  await worker.syncAlarm();await worker.wake();assert.equal(starts,0);assert.equal(navigations,0);
} else if(scenario==='legacy'||scenario==='corrupt') {
  if(scenario==='legacy')data.saArticleBodyRecovery={status:'running',items:[{article_id:'1000'}]};
  else data[key]={schema_version:999,job_id:'x'};
  await worker.syncAlarm();await worker.wake();assert.equal(starts,0);assert.equal(navigations,0);
} else if(scenario==='lost_start') {
  loseStart=true;await start();worker=make();await worker.syncAlarm();await turns();
  assert.equal(saved.size,8);assert.equal(starts,2);assert.equal(job.request_id,'request-1');
} else {
  await start();assert.equal(starts,1);
  if(scenario==='cancel_read') hook=()=>worker.cancel(job.id);
  if(scenario==='cancel_offline') {
    offline=true;const result=await worker.cancel(job.id);assert.equal(data[key].cancel_requested,true);
    assert.equal(result.cancel_pending,true);
    assert.equal((await worker.wake()).status,'error');
    assert.ok(alarms.has(alarm));
    offline=false;worker=make();await worker.syncAlarm();
  }
  if(scenario==='uncertain') pending={request_id:'unknown'};
  if(scenario==='cooldown')deadline=now+6*3600*1000;
  if(scenario==='login')restricted=true;
  if(scenario==='owner_change')ownerChanged=true;
  if(scenario==='checkpoint_loss')loseCheckpoint=true;
  if(scenario==='duplicates')await Promise.all([worker.wake(),worker.wake(),worker.wake()]);
  if(scenario==='restart') {await worker.wake();worker=make();await worker.syncAlarm();}
  if(scenario==='login') {
    await worker.wake();now+=86400000;await worker.wake();assert.equal(navigations,0);
    restricted=false;await worker.wake();assert.equal(navigations,0);
    await worker.resume(job.id);
  }
  if(scenario==='cooldown') {await worker.wake();assert.equal(navigations,0);assert.equal(alarms.get(alarm).when,deadline);}
  await turns();
  if(scenario.startsWith('cancel_')) {
    assert.equal(navigations,scenario==='cancel_save'?1:0);
    assert.equal(job.state,'cancelled');worker=make();await worker.wake();
    assert.equal(navigations,scenario==='cancel_save'?1:0);
  } else if(['uncertain','owner_change'].includes(scenario)) assert.equal(navigations,0);
  else {
    assert.equal(saved.size,scenario==='partial'?7:8);
    assert.equal(job.state,scenario==='partial'?'partial':'complete');
    assert.ok(now-Date.parse('2026-09-28T00:00:00Z')>30*60000);
    assert.ok(!alarms.has(alarm));
    for(let i=1;i<events.length;i++) if(events[i].startsWith('navigate:')&&events.slice(0,i).some(e=>e.startsWith('navigate:')))
      assert.ok(events.slice(events.slice(0,i).findLastIndex(e=>e.startsWith('navigate:'))+1,i).includes('financial'));
  }
}
console.log(JSON.stringify({startRequests:starts,uniqueSavedArticles:saved.size,navigations,
  nativeCalls:events.filter(e=>!e.includes(':')),storage:data[key]||null}));

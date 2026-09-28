// Production financial workers over shared durable intent and real loopback native authority.
import fs from 'node:fs';
import vm from 'node:vm';
import readline from 'node:readline';
import { randomUUID } from 'node:crypto';

const [baseline,candidate,url] = process.argv.slice(2);
let saved = {}, api, clock, client, alarms = [];
const clone = value => structuredClone(value);
async function rpc(message) {
  const response = await fetch(url+'/rpc',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(message)});
  return response.json();
}
async function control(operation,extra={}) { return rpc({...extra,operation,client}); }
const deps = {
  now:()=>clock,
  storage:{async get(key){return {[key]:clone(saved[key])};},async set(value){Object.assign(saved,clone(value));}},
  alarms:{async clear(){},async create(name,value){alarms.push({name,...value});}},
  control,
  resolveWatchlist:async()=>({status:'ok',tickers:['AAPL','AMD'],total_count:2,unsupported:[]}),
  runScope:async(scope,mode,admitted,_observe,interval_days,requested_at,force)=>{
    if(!await admitted())return {status:'cancelled'};
    const owner=await control('status');
    const task=await control('begin_task',{generation:owner.generation,request_id:randomUUID(),
      task_operation:'company_financial_capture',mode,trigger:'manual',intent_revision:saved.companyFinancialRefresh.intent_revision,
      build:'midfill-test',protocol_version:2,scope,interval_days,requested_at,force});
    if(task.status==='reused')return {...task,status:'ok'};
    if(task.status!=='ok')return task;
    const auth={generation:owner.generation,token:task.token};
    const navigation=await control('admit_navigation',{...auth,navigation_id:randomUUID(),kind:'create',destination_class:'financials'});
    if(!navigation.allowed)throw Error(JSON.stringify(navigation));
    const receipt=await rpc({operation:'fixture_save',scope});
    const done=await control('finish_task',{...auth,cleanup_confirmed:true,result:receipt});
    if(done.status!=='ok')throw Error(JSON.stringify(done));
    await rpc({operation:'fixture_receipt',scope,receipt:done});
    return receipt;
  },
};
function load(version) {
  const context=vm.createContext({console,Date,Set,Map,Promise,Math,Number,JSON});
  vm.runInContext(fs.readFileSync(version==='baseline'?baseline:candidate,'utf8'),context);
  api=context.SACompanyRefresh.create(deps);
}
async function command(message) {
  if(message.operation==='initialize') {
    clock=message.now;client=message.client;load('baseline');
    saved={companyCollectorIdentity:client,alphaPicksAutoSyncEnabled:true,alphaPicksAutoSyncIntervalMinutes:60,
      marketNewsAutoSyncEnabled:true,marketNewsAutoSyncIntervalMinutes:'auto',alphaPicksAutoSyncRevision:7,marketNewsAutoSyncRevision:9};
    await api.configure({enabled:message.scheduled,target_mode:'watchlist',tickers:[],
      statements:['income_statement','balance_sheet'],views:['annual'],interval_days_by_view:{annual:30,quarterly:30},financial_gap_seconds:60});
  } else if(message.operation==='reload') {load(message.version); await api.syncAlarm();}
  else if(message.operation==='run') await api.run({scheduled:message.scheduled===true});
  else if(message.operation==='clock') clock=message.now;
  else if(message.operation==='cancel') await api.cancelQueue();
  else if(message.operation==='configure') await api.configure({...saved.companyFinancialRefresh.config,enabled:false,tickers:[],views:['quarterly']});
  else if(message.operation==='retry') {
    const key=saved.companyFinancialRefresh.pending_scopes.at(-1);
    saved.companyFinancialRefresh.records[key]={last_error:'sa_company_refresh_failed',retry_after:new Date(clock+21600000).toISOString(),failures:1};
  }
  return {browser:clone(saved),alarms,status:await api.status()};
}
for await(const line of readline.createInterface({input:process.stdin,crlfDelay:Infinity})) {
  try { process.stdout.write(JSON.stringify(await command(JSON.parse(line)))+'\n'); }
  catch(error) { process.stdout.write(JSON.stringify({fixture_error:String(error),stack:error.stack})+'\n'); }
}

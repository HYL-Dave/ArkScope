// Loaded only into generated offline test packages, after the production background.
// Native transport and provider pages are fakes; queue, authority, alarms and storage are real.
async function fixtureRpc(message) {
  const response = await fetch(ARK_FIXTURE_URL + '/rpc', {
    method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(message),
  });
  return response.json();
}
companyCollectorControl = async function(operation, extra) {
  const result = await fixtureRpc(Object.assign({},extra || {},{operation,client:ARK_FIXTURE_CLIENT}));
  if(operation === 'admit_navigation' && (await chrome.storage.local.get('fixtureLoseReply')).fixtureLoseReply) {
    await chrome.storage.local.set({fixtureLoseReply:false});
    throw new Error('lost_native_reply');
  }
  return result;
};
sendNativeMessage2 = async function(message) {
  if(message.action==='sa_acquisition_control')return companyCollectorControl(message.operation,message);
  if(message.action==='get_company_watchlist')return {status:'ok',tickers:['AAPL','AMD'],total_count:2,unsupported:[],sources_by_ticker:{}};
  return {status:'error',error_code:'offline_fixture_action_disabled'};
};
runCoordinatedCompanyScope = async function(scope,mode,admitted) {
  if(!await admitted())return {status:'cancelled'};
  let tab;
  try {
    tab=await managedSaTabs.create({url:'https://seekingalpha.com/symbol/'+scope.ticker+'/income-statement',active:false});
    return await fixtureRpc({operation:'fixture_save',ticker:scope.ticker});
  } finally { if(tab)await safeRemoveTab(tab.id); }
};
async function fixtureNews(count) {
  return enqueueSaSyncJob({displayName:'Offline news',operation:'market_news_sync',mode:'quick'},async function() {
    let saved=0;
    try {
      for(let index=0;index<count;index++) {
        const tab=await managedSaTabs.create({url:'https://seekingalpha.com/news/'+index,active:false});
        await safeRemoveTab(tab.id);saved++;
      }
    } catch(error) {
      if(error.name!=='SAAcquisitionStop')throw error;
      return Object.assign({},error.detail,{detail_fetched:saved,completed_phases:['listing','metadata']});
    }
    return {status:'ok',saved:0,detail_fetched:saved};
  });
}
chrome.runtime.onMessage.addListener(function(message,sender,respond) {
  if(message.action!=='offline_fixture')return;
  (async function(){
    const command=message.command;
    if(command==='activate') {
      const state=await companyCollectorControl('status');
      return activateSaUpdates({config:{enabled:false,target_mode:'watchlist',tickers:[],statements:['income_statement'],views:['annual'],
        interval_days_by_view:{annual:7,quarterly:7},financial_gap_seconds:15},policy:{hour_limit:20,day_limit:100,hour_reserve:4,day_reserve:20},
        expected_generation:state.generation,confirm_activation:true,confirm_schedules:true});
    }
    if(command==='run') {
      companyFinancialRefresh.run({force:message.force===true}).then(result=>chrome.storage.local.set({fixtureRun:result}));
      return {started:true};
    }
    if(command==='news')return fixtureNews(message.count || 1);
    if(command==='closed_picks')return enqueueSaSyncJob({operation:'alpha_picks_sync',mode:'quick'},async()=>{
      const target='https://seekingalpha.com/alpha-picks/picks/current';
      const tab=await managedSaTabs.create({url:target,active:false});
      await chrome.tabs.remove(tab.id);
      try {
        if(message.duringUpdate)await managedSaTabs.update(tab.id,{url:target});
        else await waitForAlphaPicksTableReady(tab.id,target);
        throw new Error('closed tab unexpectedly usable');
      } finally {await safeRemoveTab(tab.id);}
    });
    if(command==='cancel')return companyFinancialRefresh.cancelQueue();
    if(command==='lose_reply'){await chrome.storage.local.set({fixtureLoseReply:true});return fixtureNews(1);}
    if(command==='schedules') {
      await setAlphaPicksAutoSyncEnabled(true,30);
      await setMarketNewsAutoSyncEnabled(true,60);
      return companyFinancialRefresh.configure({...((await companyFinancialRefresh.status()).config),enabled:true});
    }
    if(command==='restrict')return enqueueSaSyncJob({operation:'market_news_sync',mode:'quick'},async()=>{
      await observeSaRestriction(message.reason);return {status:'error',error_code:message.reason};
    });
    if(command==='recover') {
      const state=await companyCollectorControl('status');
      return handleAcquisitionControl({action:'recover_sa_acquisition',expected_generation:state.generation,confirm_stopped:true});
    }
    if(command==='policy') {
      const state=await companyCollectorControl('status');
      return companyCollectorControl('configure',{expected_generation:state.generation,confirm_activation:true,
        financial_gap_seconds:15,policy:message.policy});
    }
    if(command==='alarm') {await chrome.alarms.create(SACompanyRefresh.alarm,{when:Date.now()+500});return {started:true};}
    if(command==='snapshot')return {refresh:await companyFinancialRefresh.status(),collector:await companyCollectorControl('status'),
      stored:await chrome.storage.local.get(['saAcquisitionPending','companyFinancialRefresh','fixtureRun']),
      alarms:await chrome.alarms.getAll(),badge:await chrome.action.getBadgeText({}),tabs:await chrome.tabs.query({})};
    throw new Error('unknown fixture command');
  })().then(respond,error=>respond({fixture_error:String(error)}));
  return true;
});

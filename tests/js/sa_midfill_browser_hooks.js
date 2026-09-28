// Only provider extraction and native transport are replaced. Production startup,
// intent, queue, admission, tab cleanup, alarms and extension storage remain live.
async function midfillRpc(message) {
  const response = await fetch(ARK_FIXTURE_URL + '/rpc', {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(message),
  });
  const result = await response.json();
  if (result.fixture_error) throw Error(result.fixture_error);
  return result;
}
sendNativeMessage2 = async function(message) {
  if (['sa_acquisition_control','article_body_recovery_control','preview_article_body_recovery'].includes(message.action)) {
    return midfillRpc(message);
  }
  if (message.action === 'get_company_watchlist') return {status:'ok',tickers:['AAPL','AMD'],total_count:2,unsupported:[]};
  return {status:'error',error_code:'offline_fixture_action_disabled'};
};
runCoordinatedCompanyScope = async function(scope,mode,admitted) {
  if (!await admitted()) return {status:'cancelled'};
  let tab;
  try {
    tab = await managedSaTabs.create({url:'https://seekingalpha.com/symbol/'+scope.ticker+'/income-statement',active:false});
    return await midfillRpc({operation:'fixture_save',scope});
  } finally { if(tab) await safeRemoveTab(tab.id); }
};
if (ARK_FIXTURE_VERSION === 'candidate') captureArticleBodyRecovery = async function(target) {
  let tab;
  try {
    tab = await managedSaTabs.create({url:'https://seekingalpha.com/article/'+target.article_id+'-fixture',active:false});
    return await midfillRpc({operation:'fixture_body_save',article_id:target.article_id});
  } finally { if(tab) await safeRemoveTab(tab.id); }
};
const midfillKeys = ['companyFinancialRefresh','companyCollectorIdentity','saAcquisitionLedger','saAcquisitionPending',
  'saAcquisitionRestriction','alphaPicksAutoSyncEnabled','alphaPicksAutoSyncIntervalMinutes','alphaPicksAutoSyncRevision',
  'marketNewsAutoSyncEnabled','marketNewsAutoSyncIntervalMinutes','marketNewsAutoSyncRevision'];
chrome.runtime.onMessage.addListener(function(message,sender,respond) {
  if(message.action !== 'midfill_fixture') return;
  (async function() {
    if(message.command === 'initialize') {
      // This is the only setup write; reload deliberately never invokes it.
      await companyCollectorControl('status');
      await chrome.storage.local.set({
        alphaPicksAutoSyncEnabled:true,alphaPicksAutoSyncIntervalMinutes:60,alphaPicksAutoSyncRevision:7,
        marketNewsAutoSyncEnabled:true,marketNewsAutoSyncIntervalMinutes:'auto',marketNewsAutoSyncRevision:9});
      const configured = await companyCollectorControl('configure',{expected_generation:0,confirm_activation:true,
        financial_gap_seconds:60,policy:{hour_limit:null,day_limit:null,hour_reserve:0,day_reserve:0}});
      if(configured.status !== 'ok') throw Error(JSON.stringify(configured));
      const selected = await companyCollectorControl('select',{expected_generation:configured.generation,confirm_schedules:true});
      if(selected.status !== 'ok') throw Error(JSON.stringify(selected));
      await companyFinancialRefresh.configure({enabled:message.scheduled,target_mode:'watchlist',tickers:[],
        statements:['income_statement','balance_sheet'],views:['annual'],
        interval_days_by_view:{annual:30,quarterly:30},financial_gap_seconds:60});
    } else if(message.command === 'run') await companyFinancialRefresh.run({scheduled:false});
    else if(message.command === 'clock') ARK_FIXTURE_CLOCK = message.now;
    else if(message.command === 'body_start') {
      const preview = await articleBodyRecovery.preview();
      return articleBodyRecovery.start(preview.manifest_id);
    } else if(message.command === 'body_wake') return articleBodyRecovery.wake();
    else if(message.command === 'body_cancel') return articleBodyRecovery.cancel(message.job_id);
    else if(message.command === 'news') return enqueueSaSyncJob({operation:'market_news_sync',mode:'quick'},async()=>{
      const tab = await managedSaTabs.create({url:'https://seekingalpha.com/news/fixture',active:false});
      await safeRemoveTab(tab.id);
      return {status:'ok',saved:1,detail_fetched:1};
    });
    else if(message.command !== 'snapshot') throw Error('unknown command');
    return {version:ARK_FIXTURE_VERSION,identity:await companyCollectorIdentity,browser:await chrome.storage.local.get(midfillKeys),
      refresh:await companyFinancialRefresh.status(),alarms:await chrome.alarms.getAll()};
  })().then(respond,error=>{
    // The immutable baseline throws after persisting intent/success. Keep that
    // known timer defect explicit; candidate failures are never accepted.
    if (ARK_FIXTURE_VERSION === 'baseline' && String(error.stack).includes('company_refresh.js:185:')
        && (String(error).includes("'setTimeout' called on an object") || String(error) === 'TypeError: Illegal invocation')) {
      respond({baseline_timer_error:String(error)});
    } else respond({fixture_error:String(error),stack:error.stack});
  });
  return true;
});

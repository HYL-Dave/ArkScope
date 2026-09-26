"""Admitted context for extractor-only tests; authority tests use the real client."""

ADMITTED_TASK = """
saAcquisitionTask = {
  operation:'alpha_picks_sync', ownedTabs:new Set(), stop:null,
  interrupt(detail) {this.stop=this.stop || detail;},
  async navigate(_request, perform) { return perform(); },
  async observeRestriction(reason) { this.stop={status:'error',reason:'site_paused',error_code:reason}; },
};
chrome.alarms.clear = async () => {};
"""

AUTHORITY = """
if (!chrome.runtime.connectNative) chrome.runtime.connectNative = () => {
  const messages=new Set();
  return {onMessage:{addListener:fn=>messages.add(fn),removeListener:fn=>messages.delete(fn)},
    onDisconnect:{addListener(){},removeListener(){}},
    postMessage(){Promise.resolve().then(()=>messages.forEach(fn=>fn({status:'ok'})));},disconnect(){}};
};
const admittedState = {status:'ok',is_owner:true,ledger_id:'d'.repeat(32),generation:1,policy:{}};
let authorityReply = null;
companyCollectorControl = async (operation, message) => {
  if (authorityReply) {
    const reply = await authorityReply(operation,message);
    if (reply) return reply;
  }
  if (operation==='status') return admittedState;
  if (operation==='begin_task') return {status:'ok',token:'a'.repeat(32),task_id:'b'.repeat(32),generation:1};
  if (operation==='admit_navigation') return {status:'ok',allowed:true,replayed:false,attempt_id:'c'.repeat(32)};
  if (operation==='finish_task') return {status:'ok',acquisition:{}};
  return admittedState;
};
chrome.alarms.clear = async () => {};
async function coordinatedScope(scope,mode,admitted,observeFailure,intervalDays,diagnostics) {
  return saAcquisition.runTask({operation:'company_financial_capture',mode,scope,interval_days:intervalDays}, async task => {
    saAcquisitionTask=task;
    try { return await runCoordinatedCompanyScope(scope,mode,admitted,observeFailure,intervalDays,diagnostics); }
    finally { saAcquisitionTask=null; }
  });
}
"""

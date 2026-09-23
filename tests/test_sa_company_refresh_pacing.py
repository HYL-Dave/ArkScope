"""Preview and continuation use source scopes and native deadlines, not UI time."""

import pytest

from tests.test_sa_company_refresh import probe, WATCHLIST


def test_preview_is_read_only_and_respects_independent_check_intervals():
    result = probe("""
      await api.run(true);
      const selection={...config,interval_days_by_view:{annual:30,quarterly:7},financial_gap_seconds:15};
      await api.configure(selection);
      clock += 8*86400000;
      const before=JSON.stringify(saved);
      const first=await api.preview(selection);
      const second=await api.preview(selection);
      const after=JSON.stringify(saved);
      clock += 86400000;
      const later=await api.preview(selection);
      return {first,second,later,before,after,calls};
    """)
    assert result["before"] == result["after"]
    assert result["first"] == result["second"]
    assert result["first"]["counts"] == {"missing": 0, "due": 1, "reusable": 1, "blocked": 0}
    assert result["first"]["scopes"] == result["later"]["scopes"]
    assert len(result["calls"]) == 2


def test_regular_update_now_is_due_only_and_does_not_enable_scheduling():
    result = probe(WATCHLIST + """
      await api.noteSuccess({ticker:'AMD',statement:'income_statement',view:'annual'},
        {currency:'USD',observation_id:'a'.repeat(64)});
      await api.run({force:false});
      return {calls,status:await api.status()};
    """)
    assert result["calls"][0]["scope"] == {"ticker": "AMD", "statement": "income_statement", "view": "quarterly"}
    assert result["status"]["pending_count"] == 2
    assert result["status"]["config"]["enabled"] is False


@pytest.mark.parametrize("gap", [15, 30, 60])
def test_native_deadline_controls_timer_and_alarm_and_survives_cancellation(gap):
    result = probe(WATCHLIST + """
      let nativeDeadline=null;
      deps.control=async()=>({status:'ok',is_owner:true,policy:{},next_financial_at:nativeDeadline});
      const timers=[];const cleared=[];
      deps.setTimer=(fn,ms)=>{timers.push({fn,ms});return timers.length;};
      deps.clearTimer=id=>cleared.push(id);
      deps.runScope=async scope=>{
        calls.push(scope);
        nativeDeadline=new Date(clock+GAP*1000).toISOString();
        return {status:'ok',currency:'USD',observation_id:'a'.repeat(64)};
      };
      await api.run({force:false});
      const checkpoint=JSON.parse(JSON.stringify(saved));
      const wait=timers.at(-1).ms;
      const alarm=alarms.at(-1).when;
      const oldTimer=timers.at(-1).fn;
      clock += GAP*1000-1;
      await api.run({scheduled:true});
      const early=calls.length;
      const restarted=SACompanyRefresh.create(deps);
      await restarted.syncAlarm();
      clock+=1;
      await timers.at(-1).fn();
      await restarted.cancelQueue();
      await oldTimer();
      return {wait,alarm,checkpoint,early,calls,cleared,status:await restarted.status()};
    """.replace("GAP", str(gap)))
    assert result["wait"] == gap * 1000
    assert result["alarm"] == 1790035200000 + gap * 1000
    assert result["checkpoint"]["companyFinancialRefresh"]["next_wake_at"] == result["alarm"]
    assert result["early"] == 1
    assert len(result["calls"]) == 2
    assert result["status"]["pending_count"] == 0


def test_watchlist_preview_shows_scope_cost_before_saving():
    result = probe(WATCHLIST + """
      members=Array.from({length:180},(_,i)=>'T'+i);
      const selection={...config,target_mode:'watchlist',tickers:[],statements:['income_statement','balance_sheet','cash_flow_statement'],financial_gap_seconds:15};
      const annual=await api.preview({...selection,views:['annual']});
      const both=await api.preview({...selection,views:['annual','quarterly']});
      return {annual,both,calls};
    """)
    assert result["annual"]["counts"]["missing"] == 540
    assert result["both"]["counts"]["missing"] == 1080
    assert result["both"]["pacing_lower_bound_seconds"] == 1079 * 15
    assert result["both"]["first_fill"] is True
    assert result["both"]["observed_duration"]["sample_count"] == 0
    assert result["calls"] == []


def test_invalid_gaps_and_intervals_do_not_replace_accepted_intent():
    result = probe("""
      const before=JSON.stringify(saved);const errors=[];
      for (const gap of [0,-1,NaN,Infinity,2147484,true,'15']) {
        try {await api.configure({...config,financial_gap_seconds:gap});}
        catch(error) {errors.push(error.message);}
      }
      for (const intervals of [null,{annual:0,quarterly:7},{annual:7,quarterly:1.5}]) {
        try {await api.configure({...config,interval_days_by_view:intervals});}
        catch(error) {errors.push(error.message);}
      }
      return {errors,before,after:JSON.stringify(saved)};
    """)
    assert result["errors"] == ["sa_company_schedule_invalid"] * 10
    assert result["before"] == result["after"]


def test_native_site_pause_cannot_be_resumed_by_force_refresh():
    result = probe("""
      const operations=[];
      deps.control=async operation=>{operations.push(operation);return {status:'ok',is_owner:true,paused_reason:'login_required'};};
      await api.run({force:true});
      return {operations,calls};
    """)
    assert result["calls"] == []
    assert "resume" not in result["operations"]


@pytest.mark.parametrize("waiting", ["pacing", "active"])
def test_manual_request_during_shared_wait_is_saved_and_resumes_without_another_click(waiting):
    result = probe(WATCHLIST + """
      const deadline=new Date(clock+15000).toISOString();
      let state={status:'ok',is_owner:true,policy:{},next_financial_at:WAIT === 'pacing' ? deadline : null,
        active:WAIT === 'active' ? {operation:'market_news_sync'} : null};
      deps.control=async()=>state;
      await api.run({force:true});
      const queued=await api.status();
      const before=calls.length;
      clock+=15000;state={...state,active:null,next_financial_at:null};
      const restarted=SACompanyRefresh.create(deps);
      await restarted.run({scheduled:true});
      return {queued,before,calls,after:await restarted.status()};
    """.replace("WAIT", repr(waiting)))
    assert result["queued"]["pending_count"] == 4
    assert result["before"] == 0
    assert len(result["calls"]) == 1
    assert result["after"]["pending_count"] == 3


def test_cancel_during_initial_native_read_cannot_be_undone_by_its_late_reply():
    result = probe(WATCHLIST + """
      let release,entered;const enteredGate=new Promise(r=>entered=r);
      const gate=new Promise(r=>release=r);let reads=0;
      deps.control=async()=>{if(++reads===1){entered();await gate;}return {status:'ok',is_owner:true,policy:{}};};
      const running=api.run({force:true});await enteredGate;
      await api.cancelQueue();release();await running;
      return {calls,status:await api.status()};
    """)
    assert result["calls"] == []
    assert result["status"]["pending_count"] == 0


def test_authority_upgrade_requirement_remains_visible_without_reinitializing():
    result = probe("""
      const operations=[];
      deps.control=async operation=>{operations.push(operation);return {status:'error',error_code:'sa_acquisition_upgrade_required'};};
      return {status:await api.status(),operations};
    """)
    assert result["status"]["collector"]["error_code"] == "sa_acquisition_upgrade_required"
    assert result["operations"] == ["status"]


def test_pending_scope_backoff_does_not_block_other_targets_or_poll_every_second():
    result = probe(WATCHLIST + """
      members=['AAPL','AMD'];
      await api.configure({...config,target_mode:'watchlist',tickers:[],views:['annual'],enabled:false});
      const retry=clock+6*3600000;
      deps.runScope=async scope=>{
        calls.push(scope.ticker);
        if(scope.ticker==='AAPL' && clock<retry)return {status:'deferred',deferral_kind:'scope',
          error_code:'sa_company_refresh_interrupted',retry_after:new Date(retry).toISOString()};
        return {status:'ok',observation_id:'a'.repeat(64),currency:'USD'};
      };
      await api.run({force:true});
      await api.run({scheduled:true});
      const afterOther=await api.status();const wake=alarms.at(-1).when;
      await api.run({scheduled:true});
      const early=calls.slice();
      clock=retry;await api.run({scheduled:true});
      return {calls,early,afterOther,wake,retry,final:await api.status()};
    """)
    assert result["early"] == ["AAPL", "AMD"]
    assert result["afterOther"]["pending_count"] == 1
    assert result["wake"] == result["retry"]
    assert result["calls"] == ["AAPL", "AMD", "AAPL"]
    assert result["final"]["pending_count"] == 0

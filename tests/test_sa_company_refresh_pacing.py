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

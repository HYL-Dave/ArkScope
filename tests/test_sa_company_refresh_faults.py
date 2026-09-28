"""A rejected table is not evidence that every financial page is broken."""

import json

import pytest

from tests.test_sa_company_refresh import WATCHLIST, probe


@pytest.mark.parametrize("code", ["layout_unrecognized", "structure_changed", "identity_mismatch", "units_unrecognized", "value_unrecognized"])
def test_one_parser_failure_preserves_error_and_continues_other_ticker_after_restart(code):
    result = probe(WATCHLIST + """
      await api.configure({...saved.companyFinancialRefresh.config,views:['annual']});
      deps.runScope = async scope => {
        calls.push(scope.ticker);
        return scope.ticker === 'AMD' ? {status:'error',error_code:CODE}
          : {status:'ok',currency:'USD',observation_id:'b'.repeat(64)};
      };
      await api.run({force:false});
      await SACompanyRefresh.create(deps).run({scheduled:true});
      return {calls,status:await api.status(),records:saved.companyFinancialRefresh.records};
    """.replace("CODE", json.dumps("sa_company_" + code)))
    assert result["calls"] == ["AMD", "AAPL"]
    assert result["status"]["paused_reason"] is None
    assert result["status"]["pending_count"] == 0
    assert result["records"]["AMD/income_statement/annual"]["last_error"] == "sa_company_" + code
    assert result["records"]["AMD/income_statement/annual"]["review_required"] is True
    assert not result["records"]["AMD/income_statement/annual"].get("observation_id")
    assert result["records"]["AAPL/income_statement/annual"]["observation_id"] == "b" * 64


@pytest.mark.parametrize("threshold,attempted", [(0, 4), (2, 2), (3, 3)])
def test_distinct_ticker_threshold_is_configurable_and_durable(threshold, attempted):
    result = probe(WATCHLIST + """
      members=['AMD','AAPL','MSFT','BAC'];
      deps.control=async()=>({status:'ok',is_owner:true,financial_settings:{values:{parser_failure_ticker_threshold:THRESHOLD},error_code:null}});
      await api.configure({...saved.companyFinancialRefresh.config,views:['annual']});
      deps.runScope=async scope=>{calls.push(scope.ticker);return {status:'error',error_code:'sa_company_layout_unrecognized'};};
      await api.run({force:false});
      for(let i=0;i<4;i++)await SACompanyRefresh.create(deps).run({scheduled:true});
      return {calls,status:await api.status()};
    """.replace("THRESHOLD", str(threshold)))
    assert result["calls"] == ["AMD", "AAPL", "MSFT", "BAC"][:attempted]
    assert result["status"]["paused_reason"] == ("sa_company_parser_failures" if threshold else None)


def test_success_resets_only_its_own_statement_and_period_streak():
    result = probe(WATCHLIST + """
      members=['AMD','AAPL','MSFT','BAC'];
      deps.runScope=async scope=>{
        calls.push(scope.ticker+'/'+scope.view);
        return scope.view === 'annual' ? {status:'error',error_code:'sa_company_layout_unrecognized'}
          : {status:'ok',currency:'USD',observation_id:'b'.repeat(64)};
      };
      await api.run({force:false});
      for(let i=0;i<8;i++)await SACompanyRefresh.create(deps).run({scheduled:true});
      return {calls,status:await api.status()};
    """)
    assert result["calls"] == ["AMD/annual", "AMD/quarterly", "AAPL/annual", "AAPL/quarterly", "MSFT/annual"]
    assert result["status"]["paused_reason"] == "sa_company_parser_failures"


def test_same_kind_success_breaks_failure_streak():
    result = probe(WATCHLIST + """
      members=['AMD','AAPL','MSFT','BAC'];
      await api.configure({...saved.companyFinancialRefresh.config,views:['annual']});
      deps.runScope=async scope=>{
        calls.push(scope.ticker);
        return scope.ticker === 'AAPL' ? {status:'ok',currency:'USD',observation_id:'b'.repeat(64)}
          : {status:'error',error_code:'sa_company_layout_unrecognized'};
      };
      await api.run({force:false});
      for(let i=0;i<4;i++)await SACompanyRefresh.create(deps).run({scheduled:true});
      return {calls,status:await api.status()};
    """)
    assert result["calls"] == ["AMD", "AAPL", "MSFT", "BAC"]
    assert result["status"]["paused_reason"] is None


def test_repeating_one_ticker_never_counts_as_multiple_tickers():
    result = probe(WATCHLIST + """
      members=['AMD'];
      await api.configure({...saved.companyFinancialRefresh.config,views:['annual']});
      deps.runScope=async scope=>{calls.push(scope.ticker);return {status:'error',error_code:'sa_company_layout_unrecognized'};};
      for(let i=0;i<4;i++){
        await SACompanyRefresh.create(deps).run({force:false});
        clock+=7*86400000;
      }
      return {calls,status:await api.status()};
    """)
    assert result["calls"] == ["AMD"] * 4
    assert result["status"]["paused_reason"] is None


def test_parser_failures_are_not_silently_retried_by_maintenance():
    result = probe(WATCHLIST + """
      members=['AMD'];
      await api.configure({...saved.companyFinancialRefresh.config,views:['annual'],enabled:true});
      deps.runScope=async scope=>{calls.push(scope.ticker);return {status:'error',error_code:'sa_company_layout_unrecognized'};};
      await api.run({scheduled:true});
      clock+=8*86400000;
      await SACompanyRefresh.create(deps).run({scheduled:true});
      return {calls,status:await api.status(),preview:await api.preview()};
    """)
    assert result["calls"] == ["AMD"]
    assert result["status"]["paused_reason"] is None
    assert result["preview"]["counts"]["blocked"] == 1


def test_gap_only_change_keeps_pending_order_intent_and_successes():
    result = probe(WATCHLIST + """
      await api.run({force:false});
      const before=structuredClone(saved.companyFinancialRefresh);
      await api.configure({...before.config,financial_gap_seconds:15});
      const after=structuredClone(saved.companyFinancialRefresh);
      await SACompanyRefresh.create(deps).run({scheduled:true});
      return {before,after,calls,status:await api.status()};
    """)
    for field in ("pending_scopes", "pending_requested_at", "pending_force", "intent_revision", "records"):
        assert result["after"].get(field) == result["before"].get(field), field
    assert result["after"]["config"]["financial_gap_seconds"] == 15
    assert [call["scope"]["view"] for call in result["calls"]] == ["annual", "quarterly"]
    assert result["status"]["pending_count"] == 2


def test_invalid_financial_policy_blocks_financial_only_without_replacing_intent():
    result = probe(WATCHLIST + """
      await api.run({force:false});
      const before=structuredClone(saved.companyFinancialRefresh.pending_scopes);
      deps.control=async()=>({status:'ok',is_owner:true,financial_settings:{values:null,error_code:'sa_financial_settings_invalid'}});
      await api.run({scheduled:true});
      return {calls,before,after:saved.companyFinancialRefresh.pending_scopes,status:await api.status()};
    """)
    assert len(result["calls"]) == 1
    assert result["before"] == result["after"]
    assert result["status"]["blocked_reason"] == "sa_financial_settings_invalid"
    assert result["status"]["collector"]["status"] == "ok"


def test_legacy_parser_resume_keeps_order_successes_and_excludes_failed_scope():
    result = probe(WATCHLIST + """
      await api.run({force:false});
      const state=saved.companyFinancialRefresh;
      const failed='AMD/income_statement/quarterly';
      state.paused_reason='sa_company_layout_unrecognized';
      state.records[failed]={last_error:state.paused_reason,last_attempt_at:new Date(clock).toISOString(),failures:1};
      const before=structuredClone(state);
      await api.resumeParser();
      const after=structuredClone(saved.companyFinancialRefresh);
      await SACompanyRefresh.create(deps).run({scheduled:true});
      return {before,after,calls,status:await api.status()};
    """)
    assert result["after"]["paused_reason"] is None
    assert result["after"]["pending_scopes"] == ["AAPL/income_statement/annual", "AAPL/income_statement/quarterly"]
    assert result["after"]["intent_revision"] == result["before"]["intent_revision"]
    assert result["after"]["records"]["AMD/income_statement/annual"] == result["before"]["records"]["AMD/income_statement/annual"]
    assert result["after"]["records"]["AMD/income_statement/quarterly"]["review_required"] is True
    assert result["calls"][-1]["scope"]["ticker"] == "AAPL"


@pytest.mark.parametrize("restriction", [{"paused_reason": "login_required"}, {"paused_reason": "human_verification_required"},
    {"rate_limited": True}, {"capability_pauses": {"financials": "access_restricted"}}, {"is_owner": False}, {"active": {"task_id": "busy"}}])
def test_parser_resume_never_bypasses_shared_restrictions_or_ownership(restriction):
    result = probe(WATCHLIST + """
      saved.companyFinancialRefresh.paused_reason='sa_company_layout_unrecognized';
      deps.control=async()=>({status:'ok',is_owner:true,generation:7,...RESTRICTION});
      const before=JSON.stringify(saved);
      const result=await api.resumeParser(7);
      return {result,before,after:JSON.stringify(saved),calls};
    """.replace("RESTRICTION", json.dumps(restriction)))
    assert result["result"]["status"] != "ok"
    assert result["before"] == result["after"]
    assert result["calls"] == []


def test_access_resume_does_not_clear_an_independent_parser_pause():
    result = probe(WATCHLIST + """
      saved.companyFinancialRefresh.paused_reason='sa_company_parser_failures';
      await api.resume();
      return await api.status();
    """)
    assert result["paused_reason"] == "sa_company_parser_failures"


def test_parser_resume_rejects_stale_generation_without_touching_queue():
    result = probe(WATCHLIST + """
      saved.companyFinancialRefresh.paused_reason='sa_company_layout_unrecognized';
      deps.control=async()=>({status:'ok',is_owner:true,generation:8});
      const before=JSON.stringify(saved);
      const result=await api.resumeParser(7);
      return {result,before,after:JSON.stringify(saved)};
    """)
    assert result["result"]["error_code"] == "sa_acquisition_generation_stale"
    assert result["before"] == result["after"]


def test_parser_resume_skips_held_scopes_without_recreating_completed_work():
    result = probe(WATCHLIST + """
      members=['AMD','AAPL','MSFT','BAC'];
      await api.configure({...saved.companyFinancialRefresh.config,views:['annual']});
      deps.runScope=async scope=>{calls.push(scope.ticker);return {status:'error',error_code:'sa_company_layout_unrecognized'};};
      await api.run({force:false});
      await api.run({scheduled:true});
      await api.run({scheduled:true});
      const before=await api.status();
      await api.resumeParser();
      await api.run({scheduled:true});
      return {calls,before,after:await api.status()};
    """)
    assert result["before"]["paused_reason"] == "sa_company_parser_failures"
    assert result["calls"] == ["AMD", "AAPL", "MSFT", "BAC"]
    assert result["after"]["paused_reason"] is None
    assert result["after"]["pending_count"] == 0


def test_gap_change_during_success_readback_does_not_lose_success_or_retry_it():
    result = probe(WATCHLIST + """
      let signal,release;
      const entered=new Promise(resolve=>{signal=resolve;});
      const wait=new Promise(resolve=>{release=resolve;});
      deps.resolveWatchlist=async()=>{signal();await wait;return {status:'ok',tickers:members,total_count:members.length};};
      const success=api.noteSuccess({ticker:'AMD',statement:'income_statement',view:'annual'},
        {currency:'USD',observation_id:'b'.repeat(64)});
      await entered;
      const configuring=api.configure({...saved.companyFinancialRefresh.config,financial_gap_seconds:15});
      for(let i=0;i<20;i++)await Promise.resolve();
      release();await configuring;await success;
      await api.run({force:false});
      return {calls,records:saved.companyFinancialRefresh.records};
    """)
    assert result["records"]["AMD/income_statement/annual"]["observation_id"] == "b" * 64
    assert result["calls"][0]["scope"]["view"] == "quarterly"

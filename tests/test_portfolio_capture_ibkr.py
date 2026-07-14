from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src import portfolio_capture_ibkr
from src.portfolio_capture_ibkr import read_ibkr_capture


def obj(**values):
    return SimpleNamespace(**values)


def contract(
    con_id: int = 265598,
    *,
    symbol: str = "AAPL",
    sec_type: str = "STK",
    currency: str = "USD",
    exchange: str = "NASDAQ",
):
    return obj(
        conId=con_id,
        symbol=symbol,
        secType=sec_type,
        currency=currency,
        exchange=exchange,
        primaryExchange=exchange,
        localSymbol=symbol,
        multiplier="1",
    )


def fill(
    exec_id: str = "0001.01",
    *,
    account: str = "DU123",
    con_id: int = 265598,
    commission_report=...,
    price: float = 101.25,
):
    execution = obj(
        acctNumber=account,
        execId=exec_id,
        time=datetime(2026, 7, 13, 14, 30, tzinfo=timezone.utc),
        exchange="NASDAQ",
        side="BOT",
        shares=2.0,
        price=price,
        orderId=17,
        permId=900017,
        clientId=71,
        orderRef="capture",
        liquidation=0,
        cumQty=2.0,
        avgPrice=price,
    )
    if commission_report is ...:
        commission_report = obj(
            execId=exec_id,
            commission=1.25,
            currency="USD",
            realizedPNL=12.5,
            yield_=0.0,
            yieldRedemptionDate=0,
        )
    return obj(
        contract=contract(con_id),
        execution=execution,
        commissionReport=commission_report,
    )


def position(
    *,
    account: str = "DU123",
    con_id: int = 265598,
    quantity: float = 2.0,
    avg_cost: float = 100.0,
):
    return obj(
        account=account,
        contract=contract(con_id),
        position=quantity,
        avgCost=avg_cost,
    )


def portfolio_item(
    *,
    account: str = "DU123",
    con_id: int = 265598,
    market_value: float = 205.0,
):
    return obj(
        account=account,
        contract=contract(con_id),
        position=2.0,
        marketValue=market_value,
        unrealizedPNL=5.0,
        realizedPNL=7.0,
    )


class FakeIB:
    def __init__(self):
        self.managed_accounts = ["DU123"]
        self.summary_rows = []
        self.value_rows = []
        self.fill_rows = []
        self.position_rows = []
        self.portfolio_rows = []
        self.pnl_by_account = {}
        self.pnl_requests = []
        self.pnl_cancels = []
        self.wait_timeouts = []
        self.req_executions_calls = 0

    def managedAccounts(self):
        return self.managed_accounts

    def accountSummary(self):
        return self.summary_rows

    def accountValues(self):
        return self.value_rows

    def fills(self):
        return self.fill_rows

    def reqExecutions(self, *args, **kwargs):
        self.req_executions_calls += 1
        raise AssertionError("capture issued a second execution request")

    def positions(self):
        return self.position_rows

    def portfolio(self):
        return self.portfolio_rows

    def reqPnL(self, account):
        self.pnl_requests.append(account)
        return self.pnl_by_account.get(
            account,
            obj(realizedPnL=float("nan"), unrealizedPnL=float("nan")),
        )

    def waitOnUpdate(self, timeout=0):
        self.wait_timeouts.append(timeout)
        return False

    def cancelPnL(self, account):
        self.pnl_cancels.append(account)


class FakeSource:
    def __init__(self, ib, *, connects=True):
        self._ib = ib
        self.connects = connects
        self.connect_calls = 0
        self.disconnect_calls = 0

    def connect(self):
        self.connect_calls += 1
        return self.connects

    def disconnect(self):
        self.disconnect_calls += 1


def install_source(monkeypatch, ib=None, *, connects=True):
    captured = {}
    source = FakeSource(ib if ib is not None else FakeIB(), connects=connects)

    def factory(**kwargs):
        captured.update(kwargs)
        return source

    monkeypatch.setattr(portfolio_capture_ibkr, "_source_factory", factory)
    return source, captured


def test_capture_uses_portfolio_capture_client_id_readonly_and_disconnects(
    monkeypatch,
):
    monkeypatch.setenv("IBKR_CLIENT_ID", "1")
    source, captured = install_source(monkeypatch)

    result = read_ibkr_capture()

    assert captured == {"client_id": 71, "readonly": True}
    assert source.connect_calls == 1
    assert source.disconnect_calls == 1
    assert result.position_leg.state == "complete"


def test_connect_false_returns_failed_legs_without_reading_session(monkeypatch):
    class NoSessionSource:
        connect_calls = 0
        disconnect_calls = 0

        @property
        def _ib(self):
            raise AssertionError("session read after failed connect")

        def connect(self):
            self.connect_calls += 1
            return False

        def disconnect(self):
            self.disconnect_calls += 1

    source = NoSessionSource()
    monkeypatch.setattr(
        portfolio_capture_ibkr, "_source_factory", lambda **kwargs: source
    )

    result = read_ibkr_capture()

    assert result.account_leg.state == "failed"
    assert result.execution_leg.state == "failed"
    assert result.position_leg.state == "failed"
    assert {
        result.account_leg.error_code,
        result.execution_leg.error_code,
        result.position_leg.error_code,
    } == {"ibkr_connection_failed"}
    assert result.discovered_accounts == ()
    assert source.disconnect_calls == 1

    missing, _ = install_source(monkeypatch, ib=None)
    missing._ib = None
    missing_result = read_ibkr_capture()
    assert missing_result.account_leg.error_code == "ibkr_session_missing"
    assert missing.disconnect_calls == 1


def test_account_leg_keeps_selected_fields_and_uses_unique_cached_base_currency_hint(
    monkeypatch,
):
    def summary(account, tag, value, currency):
        return obj(account=account, tag=tag, value=value, currency=currency)

    ib = FakeIB()
    ib.summary_rows = [
        summary("DU123", "NetLiquidation", "120000", "EUR"),
        summary("DU123", "NetLiquidation", "150000", "USD"),
        summary("DU123", "TotalCashValue", "22000", "EUR"),
        summary("DU123", "TotalCashValue", "25000", "USD"),
        summary("DU123", "AvailableFunds", "18000", "BASE"),
        summary("DU123", "AccruedCash", "999", "USD"),
    ]
    ib.value_rows = [
        obj(account="DU123", tag="Currency", value="USD", currency="")
    ]
    install_source(monkeypatch, ib)

    result = read_ibkr_capture()

    snapshot = result.account_snapshots[0]
    assert snapshot.base_currency == "USD"
    assert snapshot.net_liquidation == 150000.0
    assert snapshot.total_cash_value == 25000.0
    assert snapshot.available_funds == 18000.0
    assert not hasattr(snapshot, "accrued_cash")
    assert result.account_leg.state == "complete"

    ambiguous = FakeIB()
    ambiguous.summary_rows = ib.summary_rows
    ambiguous.value_rows = [
        obj(account="DU123", tag="Currency", value="USD", currency=""),
        obj(account="DU123", tag="RealCurrency", value="EUR", currency=""),
    ]
    install_source(monkeypatch, ambiguous)

    ambiguous_result = read_ibkr_capture()

    ambiguous_snapshot = ambiguous_result.account_snapshots[0]
    assert ambiguous_snapshot.base_currency is None
    assert ambiguous_snapshot.net_liquidation is None
    assert ambiguous_snapshot.available_funds == 18000.0

    mismatched = FakeIB()
    mismatched.summary_rows = [
        summary("DU123", "NetLiquidation", "120000", "EUR")
    ]
    mismatched.value_rows = [
        obj(account="DU123", tag="Currency", value="USD", currency="")
    ]
    install_source(monkeypatch, mismatched)

    mismatched_result = read_ibkr_capture()

    mismatched_snapshot = mismatched_result.account_snapshots[0]
    assert mismatched_snapshot.base_currency == "USD"
    assert mismatched_snapshot.net_liquidation is None
    assert mismatched_result.account_leg.state == "partial"


def test_account_summary_all_pseudo_account_is_not_discovered(monkeypatch):
    ib = FakeIB()
    ib.summary_rows = [
        obj(
            account="All",
            tag="NetLiquidation",
            value="350000",
            currency="USD",
        ),
        obj(
            account="DU123",
            tag="NetLiquidation",
            value="150000",
            currency="USD",
        ),
    ]
    ib.value_rows = [
        obj(account="DU123", tag="Currency", value="USD", currency="USD")
    ]
    install_source(monkeypatch, ib)

    result = read_ibkr_capture()

    assert [account.broker_account_id for account in result.discovered_accounts] == [
        "DU123"
    ]
    assert [snapshot.broker_account_id for snapshot in result.account_snapshots] == [
        "DU123"
    ]
    assert ib.pnl_requests == ["DU123"]


def test_account_values_base_sentinel_does_not_make_account_leg_partial(
    monkeypatch,
):
    ib = FakeIB()
    ib.value_rows = [
        obj(account="DU123", tag="Currency", value="BASE", currency="BASE"),
        obj(account="DU123", tag="Currency", value="USD", currency="USD"),
        obj(account="DU123", tag="RealCurrency", value="USD", currency="BASE"),
        obj(account="DU123", tag="RealCurrency", value="USD", currency="USD"),
    ]
    install_source(monkeypatch, ib)

    result = read_ibkr_capture()

    assert result.account_snapshots[0].base_currency == "USD"
    assert result.account_leg.state == "complete"


def test_daily_pnl_subscription_is_bounded_and_missing_values_stay_null(
    monkeypatch,
):
    ib = FakeIB()
    ib.managed_accounts = ["DU123", "DU456"]
    ib.pnl_by_account = {
        "DU123": obj(realizedPnL=10.5, unrealizedPnL=-2.25),
        "DU456": obj(
            realizedPnL=1.7976931348623157e308,
            unrealizedPnL=float("nan"),
        ),
    }
    install_source(monkeypatch, ib)

    result = read_ibkr_capture()

    snapshots = {
        snapshot.broker_account_id: snapshot for snapshot in result.account_snapshots
    }
    assert snapshots["DU123"].daily_realized_pnl == 10.5
    assert snapshots["DU123"].daily_unrealized_pnl == -2.25
    assert snapshots["DU456"].daily_realized_pnl is None
    assert snapshots["DU456"].daily_unrealized_pnl is None
    assert ib.pnl_requests == ["DU123", "DU456"]
    assert ib.pnl_cancels == ["DU123", "DU456"]
    assert sum(ib.wait_timeouts) <= 2.0
    assert max(ib.wait_timeouts, default=0) <= 2.0


def test_execution_leg_uses_connect_synced_fills_without_second_execution_request(
    monkeypatch,
):
    ib = FakeIB()
    ib.fill_rows = [fill()]
    install_source(monkeypatch, ib)

    result = read_ibkr_capture()

    assert ib.req_executions_calls == 0
    assert result.execution_leg.state == "complete"
    execution = result.executions[0]
    assert execution.exec_id == "0001.01"
    assert execution.order_id == 17
    assert execution.perm_id == 900017
    assert execution.execution_time_utc == "2026-07-13T14:30:00+00:00"
    assert result.commissions[0].commission == 1.25


def test_missing_commission_report_does_not_invent_zero_commission_or_pnl(
    monkeypatch,
):
    ib = FakeIB()
    ib.fill_rows = [
        fill(
            commission_report=obj(
                execId="",
                commission=0.0,
                currency="",
                realizedPNL=0.0,
                yield_=0.0,
                yieldRedemptionDate=0,
            )
        )
    ]
    install_source(monkeypatch, ib)

    result = read_ibkr_capture()

    assert len(result.executions) == 1
    assert result.commissions == ()
    assert result.execution_leg.state == "complete"


def test_position_leg_joins_positions_and_portfolio_by_account_and_conid(
    monkeypatch,
):
    ib = FakeIB()
    ib.managed_accounts = ["DU123"]
    ib.position_rows = [position(account="DU123", con_id=42)]
    ib.portfolio_rows = [
        portfolio_item(account="DU123", con_id=42, market_value=205.0),
    ]
    install_source(monkeypatch, ib)

    result = read_ibkr_capture()

    assert result.position_leg.state == "complete"
    observed = result.positions[0]
    assert observed.broker_account_id == "DU123"
    assert observed.broker_con_id == "42"
    assert observed.market_value == 205.0
    assert observed.unrealized_pnl == 5.0
    assert observed.realized_pnl == 7.0

    missing_enrichment = FakeIB()
    missing_enrichment.position_rows = [
        position(account="DU123", con_id=42),
        position(account="DU123", con_id=43),
    ]
    missing_enrichment.portfolio_rows = [
        portfolio_item(account="DU123", con_id=42, market_value=205.0),
        obj(
            account="DU123",
            contract=contract(43),
            position=2.0,
            marketValue=None,
            unrealizedPNL=None,
            realizedPNL=None,
        ),
    ]
    install_source(monkeypatch, missing_enrichment)

    missing_result = read_ibkr_capture()

    assert missing_result.position_leg.state == "partial"
    assert [row.broker_con_id for row in missing_result.positions] == ["42", "43"]
    assert missing_result.positions[0].market_value == 205.0
    assert missing_result.positions[1].market_value is None

    partially_missing = FakeIB()
    partially_missing.position_rows = [
        position(account="DU123", con_id=42),
        position(account="DU123", con_id=44),
    ]
    partially_missing.portfolio_rows = [
        portfolio_item(account="DU123", con_id=42, market_value=205.0),
        obj(
            account="DU123",
            contract=contract(44),
            position=2.0,
            marketValue=None,
            unrealizedPNL=6.0,
            realizedPNL=8.0,
        ),
    ]
    install_source(monkeypatch, partially_missing)

    partially_missing_result = read_ibkr_capture()

    assert partially_missing_result.position_leg.state == "partial"
    assert [row.broker_con_id for row in partially_missing_result.positions] == [
        "42",
        "44",
    ]
    assert partially_missing_result.positions[0].market_value == 205.0
    assert partially_missing_result.positions[1].market_value is None
    assert partially_missing_result.positions[1].unrealized_pnl == 6.0
    assert partially_missing_result.positions[1].realized_pnl == 8.0

    duplicate_positions = FakeIB()
    duplicate_positions.position_rows = [
        position(account="DU123", con_id=42),
        position(account="DU123", con_id=42),
        position(account="DU123", con_id=43),
    ]
    duplicate_positions.portfolio_rows = [
        portfolio_item(account="DU123", con_id=42, market_value=205.0),
        portfolio_item(account="DU123", con_id=43, market_value=310.0),
    ]
    install_source(monkeypatch, duplicate_positions)

    duplicate_result = read_ibkr_capture()

    assert duplicate_result.position_leg.state == "partial"
    assert [row.broker_con_id for row in duplicate_result.positions].count("42") <= 1
    assert [row.broker_con_id for row in duplicate_result.positions].count("43") == 1

    extra_portfolio = FakeIB()
    extra_portfolio.position_rows = [position(account="DU123", con_id=42)]
    extra_portfolio.portfolio_rows = [
        portfolio_item(account="DU123", con_id=42, market_value=205.0),
        portfolio_item(account="DU123", con_id=99, market_value=999.0),
    ]
    install_source(monkeypatch, extra_portfolio)

    extra_result = read_ibkr_capture()

    assert extra_result.position_leg.state == "partial"
    assert [row.broker_con_id for row in extra_result.positions] == ["42"]
    assert extra_result.positions[0].market_value == 205.0


def test_successful_empty_position_calls_are_complete(monkeypatch):
    ib = FakeIB()
    ib.managed_accounts = []
    install_source(monkeypatch, ib)

    result = read_ibkr_capture()

    assert result.position_leg.state == "complete"
    assert result.positions == ()
    assert result.discovered_accounts == ()


def test_one_failed_leg_does_not_discard_other_valid_legs(monkeypatch):
    class PartiallyFailingIB(FakeIB):
        def accountSummary(self):
            raise PermissionError("account DU-SECRET summary denied")

    ib = PartiallyFailingIB()
    ib.fill_rows = [fill()]
    ib.position_rows = [position()]
    ib.portfolio_rows = [portfolio_item()]
    install_source(monkeypatch, ib)

    result = read_ibkr_capture()

    assert result.account_leg.state == "failed"
    assert result.account_leg.error_code == "ibkr_account_summary_failed"
    assert result.account_leg.detail == "PermissionError"
    assert "DU-SECRET" not in repr(result.account_leg)
    assert result.execution_leg.state == "complete"
    assert len(result.executions) == 1
    assert result.position_leg.state == "complete"
    assert len(result.positions) == 1


def test_non_finite_provider_value_marks_the_leg_partial_and_never_zero(
    monkeypatch,
):
    class OverflowingNumber:
        def __float__(self):
            raise OverflowError("provider numeric overflow")

    ib = FakeIB()
    ib.summary_rows = [
        obj(
            account="DU123",
            tag="NetLiquidation",
            value="100000",
            currency="BASE",
        ),
        obj(
            account="DU456",
            tag="NetLiquidation",
            value=float("nan"),
            currency="BASE",
        ),
    ]
    overflowing_execution = fill("overflow", account="DU789")
    overflowing_execution.execution.permId = float("inf")
    ib.fill_rows = [
        fill("good"),
        fill("bad", account="DU456", price=float("inf")),
        overflowing_execution,
    ]
    ib.position_rows = [
        position(account="DU123", con_id=1),
        position(account="DU456", con_id=2, quantity=float("nan")),
    ]
    overflowing_position = position(account="DU789", con_id=3)
    overflowing_position.contract.conId = float("inf")
    ib.position_rows.append(overflowing_position)
    ib.portfolio_rows = [
        portfolio_item(account="DU123", con_id=1),
        portfolio_item(account="DU456", con_id=2),
    ]
    ib.pnl_by_account = {
        "DU123": obj(
            realizedPnL=OverflowingNumber(),
            unrealizedPnL=float("nan"),
        )
    }
    install_source(monkeypatch, ib)

    result = read_ibkr_capture()

    assert result.account_leg.state == "partial"
    assert [row.net_liquidation for row in result.account_snapshots] == [100000.0, None]
    assert result.execution_leg.state == "partial"
    assert [row.exec_id for row in result.executions] == ["good"]
    assert result.position_leg.state == "partial"
    assert [(row.broker_account_id, row.broker_con_id) for row in result.positions] == [
        ("DU123", "1")
    ]
    assert all(row.price != 0 for row in result.executions)

    overflowing_commission = fill("bad-commission", account="DU456")
    overflowing_commission.commissionReport.yieldRedemptionDate = float("inf")
    commission_ib = FakeIB()
    commission_ib.fill_rows = [fill("good-commission"), overflowing_commission]
    install_source(monkeypatch, commission_ib)

    commission_result = read_ibkr_capture()

    assert commission_result.execution_leg.state == "partial"
    assert [row.exec_id for row in commission_result.executions] == [
        "good-commission",
        "bad-commission",
    ]
    assert [row.exec_id for row in commission_result.commissions] == [
        "good-commission"
    ]

    pnl_ib = FakeIB()
    pnl_ib.pnl_by_account = {
        "DU123": obj(
            realizedPnL=OverflowingNumber(),
            unrealizedPnL=4.5,
        )
    }
    install_source(monkeypatch, pnl_ib)

    pnl_result = read_ibkr_capture()

    assert pnl_result.account_leg.state == "partial"
    assert pnl_result.account_snapshots[0].daily_realized_pnl is None
    assert pnl_result.account_snapshots[0].daily_unrealized_pnl == 4.5

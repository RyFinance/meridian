"""Broker adapters, mode selection and the live guards. No network: adapters
run against httpx.MockTransport, execution against an in-memory fake broker."""
from __future__ import annotations

import json
import os
import stat

import httpx
import pytest

import bot.execution as ex
from bot import broker_config
from bot.broker_execution import BrokerExecutionClient
import bot.risk_gate as rg
from bot.risk_gate import RiskGateDecision
from brokers import REGISTRY, BrokerError, OrderResult
from brokers.alpaca import Alpaca
from brokers.base import Broker, BrokerAccount
from brokers.questrade import Questrade
from brokers.schwab import Schwab
from brokers.trading212 import Trading212, from_t212, to_t212
from brokers.tradier import Tradier


def mock_client(handler):
    return lambda: httpx.Client(transport=httpx.MockTransport(handler))


# -- adapters ----------------------------------------------------------------

def test_alpaca_reads_account_and_sends_a_day_market_order():
    sent = {}

    def handler(request: httpx.Request):
        assert request.url.host == "paper-api.alpaca.markets"
        assert request.headers["APCA-API-KEY-ID"] == "PK1"
        if request.url.path == "/v2/account":
            return httpx.Response(200, json={"account_number": "PA123456", "currency": "USD", "cash": "900.5",
                                             "equity": "1000", "buying_power": "2000"})
        if request.url.path == "/v2/positions":
            return httpx.Response(200, json=[{"symbol": "MS", "qty": "3", "avg_entry_price": "180",
                                              "market_value": "540", "unrealized_pl": "-1.5"}])
        if request.url.path == "/v2/orders" and request.method == "POST":
            sent.update(json.loads(request.content))
            return httpx.Response(200, json={"id": "o1", "status": "filled", "filled_qty": "3", "filled_avg_price": "181.2"})
        raise AssertionError(request.url)

    broker = Alpaca({"key_id": "PK1", "secret_key": "s"}, "paper", mock_client(handler))
    acct = broker.account()
    assert (acct.cash, acct.equity, acct.positions[0].symbol, acct.positions[0].qty) == (900.5, 1000.0, "MS", 3.0)
    result = broker.submit_market("MS", "sell_short", 3)
    assert sent == {"symbol": "MS", "qty": "3", "side": "sell", "type": "market", "time_in_force": "day"}
    assert result.filled and result.avg_fill_price == 181.2


def test_alpaca_live_uses_the_live_host():
    hosts = []

    def handler(request):
        hosts.append(request.url.host)
        return httpx.Response(200, json={} if request.url.path == "/v2/account" else [])

    Alpaca({"key_id": "AK", "secret_key": "s"}, "live", mock_client(handler)).account()
    assert set(hosts) == {"api.alpaca.markets"}


def test_tradier_handles_a_single_position_object_and_null():
    def handler(request):
        if request.url.path.endswith("/balances"):
            return httpx.Response(200, json={"balances": {"total_cash": 50, "total_equity": 150, "margin": {"stock_buying_power": 300}}})
        return httpx.Response(200, json={"positions": {"position": {"symbol": "JNJ", "quantity": 2, "cost_basis": 500}}})

    acct = Tradier({"token": "t", "account_id": "VA1"}, "paper", mock_client(handler)).account()
    assert acct.positions[0].avg_price == 250 and acct.buying_power == 300

    def empty(request):
        if request.url.path.endswith("/balances"):
            return httpx.Response(200, json={"balances": {}})
        return httpx.Response(200, json={"positions": "null"})

    assert Tradier({"token": "t", "account_id": "VA1"}, "paper", mock_client(empty)).account().positions == []


def test_bad_credentials_surface_as_a_broker_error():
    broker = Alpaca({"key_id": "x", "secret_key": "y"}, "paper", mock_client(lambda r: httpx.Response(401)))
    with pytest.raises(BrokerError, match="rejected the credentials"):
        broker.account()


def test_capabilities_block_unsupported_orders_before_any_request():
    no_network = mock_client(lambda r: (_ for _ in ()).throw(AssertionError("no request expected")))
    with pytest.raises(BrokerError, match="short"):
        Trading212({"api_key": "k"}, "paper", no_network).submit_market("AAPL", "sell_short", 1)
    with pytest.raises(BrokerError, match="API orders"):
        Questrade({"refresh_token": "r"}, "live", no_network).submit_market("AAPL", "buy", 1)
    with pytest.raises(BrokerError, match="no paper environment"):
        Schwab({"app_key": "a", "app_secret": "b", "refresh_token": "c"}, "paper", no_network)
    with pytest.raises(BrokerError, match="zero shares"):
        Alpaca({"key_id": "x", "secret_key": "y"}, "paper", no_network).submit_market("AAPL", "buy", 0)


def test_trading212_ticker_codes_round_trip():
    assert to_t212("AAPL") == "AAPL_US_EQ" and from_t212("AAPL_US_EQ") == "AAPL"
    assert to_t212("BRK.B") == "BRK_B_US_EQ"


def test_every_registered_broker_describes_itself():
    for broker_id, cls in REGISTRY.items():
        info = cls.describe()
        assert info["id"] == broker_id and info["fields"] and set(info["can_trade"]) <= set(info["envs"])


# -- selection and live guards ------------------------------------------------

def test_credentials_are_private_and_env_overrides_them(monkeypatch):
    broker_config.save_credentials("alpaca", "paper", {"key_id": "PK1", "secret_key": "s1"})
    mode = stat.S_IMODE(os.stat(broker_config.CREDENTIALS_PATH).st_mode)
    assert mode == 0o600
    monkeypatch.setenv("MERIDIAN_ALPACA_PAPER_KEY_ID", "PK-ENV")
    assert broker_config.credentials("alpaca", "paper") == {"key_id": "PK-ENV", "secret_key": "s1"}
    with pytest.raises(BrokerError, match="missing"):
        broker_config.save_credentials("alpaca", "live", {"key_id": "AK"})


def test_live_needs_env_flag_credentials_and_the_arm_phrase(monkeypatch):
    with pytest.raises(BrokerError, match="link Alpaca"):
        broker_config.select("live", "alpaca")
    broker_config.save_credentials("alpaca", "live", {"key_id": "AK", "secret_key": "s"})
    with pytest.raises(BrokerError, match="MERIDIAN_ALLOW_LIVE"):
        broker_config.select("live", "alpaca", confirm="LIVE ALPACA")
    monkeypatch.setenv("MERIDIAN_ALLOW_LIVE", "yes")
    with pytest.raises(BrokerError, match="LIVE ALPACA"):
        broker_config.select("live", "alpaca", confirm="live")
    sel = broker_config.select("live", "alpaca", capital_usd=5000, confirm="live alpaca")
    assert sel.mode == "live" and sel.env == "live" and sel.armed_phrase == "LIVE ALPACA"
    assert broker_config.live_is_armed("alpaca") == (True, "")
    monkeypatch.setenv("MERIDIAN_ALLOW_LIVE", "no")
    assert broker_config.live_is_armed("alpaca")[0] is False


def test_paper_mode_refused_for_brokers_without_paper_orders():
    broker_config.save_credentials("questrade", "paper", {"refresh_token": "r"})
    with pytest.raises(BrokerError, match="read-only"):
        broker_config.select("paper", "questrade")
    assert broker_config.select("readonly", "questrade", env="paper").mode == "readonly"


def test_unlinking_the_active_broker_falls_back_to_the_simulator():
    broker_config.save_credentials("alpaca", "paper", {"key_id": "PK", "secret_key": "s"})
    broker_config.select("paper", "alpaca")
    broker_config.delete_credentials("alpaca", "paper")
    assert broker_config.load_selection().mode == "sim"


# -- broker execution ----------------------------------------------------------

class FakeBroker(Broker):
    id, name = "fake", "Fake"
    envs = can_trade = ("paper", "live")
    fields = ()

    def __init__(self, env="paper", price=50.0):
        super().__init__({}, env)
        self.price, self.orders = price, []

    def quote(self, symbol):
        return self.price

    def _submit(self, symbol, side, qty):
        self.orders.append((symbol, side, qty))
        return OrderResult(order_id=f"o{len(self.orders)}", status="filled", filled_qty=qty, avg_fill_price=self.price)

    def order(self, order_id):
        raise AssertionError("already filled")

    def account(self):
        return BrokerAccount(account_id="fake")


def _approved(size_fraction=0.05):
    """A passing decision of a chosen size. Registers its token the way
    risk_gate.evaluate does, so place_order's single-use check is real."""
    token = f"test-{len(rg._VALID_TOKENS)}-{size_fraction}-{id(object())}"
    rg._VALID_TOKENS.add(token)
    return RiskGateDecision(allowed=True, reason=None, detail="approved", size_fraction=size_fraction,
                            approval_token=token)


@pytest.fixture
def silent_alerts(monkeypatch):
    class Quiet:
        def alert(self, *a, **k):
            pass
    monkeypatch.setattr(ex, "build_alerter", lambda: Quiet())


def test_broker_paper_fill_books_whole_shares_at_the_broker_price(tmp_path, silent_alerts):
    broker = FakeBroker(price=50.0)
    client = BrokerExecutionClient(starting_capital=10_000, ledger_path=tmp_path / "l.jsonl").attach(broker, "paper")
    fill = client.place_order("MS", "long", _approved(0.05), entry_date="2026-10-20")  # $500 / $50
    assert broker.orders == [("MS", "buy", 10)] and fill.notional == 500.0 and fill.mode == "paper"
    record = json.loads((tmp_path / "l.jsonl").read_text().splitlines()[0])
    assert record["order_id"] == "o1" and record["qty"] == 10 and record["broker"] == "fake"

    broker.price = 55.0
    pnl = client.close_position("MS", exit_date="2026-11-17")
    assert broker.orders[-1] == ("MS", "sell", 10)
    assert pnl == pytest.approx(50.0 - (500 + 550) * 0.0005)
    replay = BrokerExecutionClient.from_ledger(starting_capital=10_000, ledger_path=tmp_path / "l.jsonl")
    assert replay.realized_pnl == pytest.approx(pnl)


def test_short_entries_and_covers_use_the_right_sides(tmp_path, silent_alerts):
    broker = FakeBroker(price=20.0)
    client = BrokerExecutionClient(starting_capital=10_000, ledger_path=tmp_path / "l.jsonl").attach(broker, "paper")
    client.place_order("IBKR", "short", _approved(0.02), entry_date="2026-10-20")
    client.close_position("IBKR", exit_date="2026-11-17")
    assert [o[1] for o in broker.orders] == ["sell_short", "buy_to_cover"]


def test_live_orders_are_capped_and_stop_when_disarmed(tmp_path, monkeypatch, silent_alerts):
    monkeypatch.setenv("MERIDIAN_ALLOW_LIVE", "yes")
    monkeypatch.setenv("MERIDIAN_LIVE_MAX_ORDER_USD", "300")
    broker_config.save_selection(broker_config.Selection(mode="live", broker="fake", env="live",
                                                         armed_phrase=broker_config.arm_phrase("fake")))
    broker = FakeBroker(env="live", price=10.0)
    client = BrokerExecutionClient(starting_capital=100_000, ledger_path=tmp_path / "l.jsonl").attach(broker, "live")
    client.place_order("MS", "long", _approved(0.05), entry_date="2026-10-20")  # wanted $5,000
    assert broker.orders == [("MS", "buy", 30)]
    assert json.loads((tmp_path / "l.jsonl").read_text().splitlines()[0])["notional_before_live_cap"] == 5000.0

    broker_config.save_selection(broker_config.Selection())  # disarmed in the desk
    with pytest.raises(PermissionError, match="not armed"):
        client.place_order("PNC", "long", _approved(0.05), entry_date="2026-10-20")
    assert len(broker.orders) == 1


def test_orders_below_one_share_are_refused_and_approval_is_single_use(tmp_path, silent_alerts):
    broker = FakeBroker(price=900.0)
    client = BrokerExecutionClient(starting_capital=1_000, ledger_path=tmp_path / "l.jsonl").attach(broker, "paper")
    with pytest.raises(BrokerError, match="less than one share"):
        client.place_order("BKNG", "long", _approved(0.05), entry_date="2026-10-20")
    assert broker.orders == []
    broker.price = 10.0
    decision = _approved(0.5)
    client.place_order("MS", "long", decision, entry_date="2026-10-20")
    with pytest.raises(PermissionError):
        client.place_order("PNC", "long", decision, entry_date="2026-10-20")

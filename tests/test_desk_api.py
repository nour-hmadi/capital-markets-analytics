"""Trade desk API: create, read, update and delete desk trades; the official book stays read-only."""
import pytest
from lxml import etree
from sqlalchemy import text

import desk_api
from desk_api import MAX_TRADES, engine
from export_xml import load_schema

EQUITY = {"instrument_type": "EQUITY_INDEX", "underlying": "INDEX_TECH", "direction": "BUY",
          "quantity": 100, "trade_date": "2025-03-03", "counterparty": "Alpha Bank"}
KEY = "test-app-key"
ALICE = {"X-User-Email": "alice@example.com", "X-App-Key": KEY}
BOB = {"X-User-Email": "bob@example.com", "X-App-Key": KEY}


@pytest.fixture
def desk(client, monkeypatch):
    """The API with an empty desk before and after each test, and the app's key set."""
    def clear():
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM desk_trades WHERE owner = 'guest' OR owner LIKE '%@example.com'"))
    monkeypatch.setattr(desk_api, "APP_KEY", KEY)
    clear()
    yield client
    clear()


def test_create_then_list(desk):
    created = desk.post("/desk/trades", json=EQUITY)
    assert created.status_code == 201
    trade = created.json()
    assert trade["trade_id"] >= "T90001"
    assert trade["valuation_date"] == "2025-12-18"
    assert [t["trade_id"] for t in desk.get("/desk/trades").json()] == [trade["trade_id"]]


def test_update_doubles_the_pnl(desk):
    trade = desk.post("/desk/trades", json=EQUITY).json()
    changed = desk.put(f"/desk/trades/{trade['trade_id']}", json={"direction": "BUY", "quantity": 200}).json()
    assert changed["quantity"] == 200
    assert changed["pnl"] == pytest.approx(2 * trade["pnl"], abs=0.02)


def test_delete_removes_the_trade(desk):
    trade_id = desk.post("/desk/trades", json=EQUITY).json()["trade_id"]
    assert desk.delete(f"/desk/trades/{trade_id}").status_code == 204
    assert desk.get("/desk/trades").json() == []
    assert desk.delete(f"/desk/trades/{trade_id}").status_code == 404


@pytest.mark.parametrize("method", ["put", "delete"])
def test_official_book_is_read_only(desk, method):
    kwargs = {"json": {"direction": "SELL", "quantity": 1}} if method == "put" else {}
    assert getattr(desk, method)("/desk/trades/T00001", **kwargs).status_code == 403


@pytest.mark.parametrize("changes, status", [
    ({"underlying": "GOV_10Y"}, 400),            # not an equity index
    ({"trade_date": "2025-03-01"}, 400),         # a Saturday
    ({"quantity": -5}, 422),                     # rejected by the request model
    ({"direction": "HOLD"}, 422),
])
def test_bad_trades_are_rejected(desk, changes, status):
    assert desk.post("/desk/trades", json=EQUITY | changes).status_code == status


def test_limit_per_visitor(desk):
    for _ in range(MAX_TRADES):
        assert desk.post("/desk/trades", json=EQUITY).status_code == 201
    assert desk.post("/desk/trades", json=EQUITY).status_code == 409


def test_desk_trade_xml_passes_the_schema(desk):
    bond = EQUITY | {"instrument_type": "BOND", "underlying": "GOV_10Y", "quantity": 1_000_000}
    trade_id = desk.post("/desk/trades", json=bond).json()["trade_id"]
    response = desk.get(f"/desk/trades/{trade_id}/xml")
    assert response.status_code == 200
    assert load_schema().validate(etree.fromstring(response.content))


def ids(desk, headers=None):
    return [t["trade_id"] for t in desk.get("/desk/trades", headers=headers).json()]


def test_signed_in_users_keep_their_own_trades(desk):
    alice = desk.post("/desk/trades", json=EQUITY, headers=ALICE).json()["trade_id"]
    guest = desk.post("/desk/trades", json=EQUITY).json()["trade_id"]
    assert ids(desk, ALICE) == [alice]
    assert ids(desk) == [guest]
    assert ids(desk, BOB) == []
    with engine.connect() as conn:
        owner = conn.execute(text("SELECT owner FROM desk_trades WHERE trade_id = :id"), {"id": alice}).scalar()
    assert owner == "alice@example.com"


def test_email_case_does_not_matter(desk):
    alice = desk.post("/desk/trades", json=EQUITY, headers=ALICE).json()["trade_id"]
    assert ids(desk, ALICE | {"X-User-Email": " Alice@Example.COM "}) == [alice]


@pytest.mark.parametrize("headers", [BOB, {}], ids=["another user", "a guest"])
def test_nobody_else_can_touch_a_users_trade(desk, headers):
    alice = desk.post("/desk/trades", json=EQUITY, headers=ALICE).json()["trade_id"]
    change = {"direction": "SELL", "quantity": 1}
    assert desk.put(f"/desk/trades/{alice}", json=change, headers=headers).status_code == 404
    assert desk.get(f"/desk/trades/{alice}/xml", headers=headers).status_code == 404
    assert desk.delete(f"/desk/trades/{alice}", headers=headers).status_code == 404
    assert ids(desk, ALICE) == [alice]


@pytest.mark.parametrize("headers", [
    {"X-User-Email": "alice@example.com"},                               # no key
    {"X-User-Email": "alice@example.com", "X-App-Key": "a-wrong-key"},
], ids=["no key", "wrong key"])
def test_only_the_app_can_act_for_a_user(desk, headers):
    assert desk.get("/desk/trades", headers=headers).status_code == 401
    assert desk.post("/desk/trades", json=EQUITY, headers=headers).status_code == 401


def test_without_a_key_on_the_server_nobody_can_sign_in(desk, monkeypatch):
    monkeypatch.setattr(desk_api, "APP_KEY", "")
    assert desk.get("/desk/trades", headers=ALICE | {"X-App-Key": ""}).status_code == 401
    assert desk.get("/desk/trades").status_code == 200                  # guests still work


def test_the_limit_is_per_person(desk):
    for _ in range(MAX_TRADES):
        assert desk.post("/desk/trades", json=EQUITY).status_code == 201
    assert desk.post("/desk/trades", json=EQUITY, headers=ALICE).status_code == 201

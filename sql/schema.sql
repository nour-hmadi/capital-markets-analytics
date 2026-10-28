-- Star schema for the capital markets project
DROP TABLE IF EXISTS fact_valuations CASCADE;
DROP TABLE IF EXISTS fact_market_prices CASCADE;
DROP TABLE IF EXISTS dim_trade CASCADE;
DROP TABLE IF EXISTS dim_date CASCADE;

CREATE TABLE dim_date (
    date        DATE PRIMARY KEY,
    year        INT  NOT NULL,
    quarter     INT  NOT NULL,
    month       INT  NOT NULL,
    month_name  TEXT NOT NULL,
    weekday     TEXT NOT NULL
);

CREATE TABLE dim_trade (
    trade_id        TEXT PRIMARY KEY,
    trade_date      DATE NOT NULL REFERENCES dim_date(date),
    desk            TEXT NOT NULL,
    instrument_type TEXT NOT NULL,
    underlying      TEXT NOT NULL,
    direction       TEXT NOT NULL CHECK (direction IN ('BUY', 'SELL')),
    quantity        NUMERIC NOT NULL CHECK (quantity > 0),
    trade_price     NUMERIC NOT NULL,
    coupon_rate     NUMERIC,
    maturity_years  INT,
    spot_at_trade   NUMERIC,
    maturity_date   DATE,
    counterparty    TEXT NOT NULL
);

CREATE TABLE fact_market_prices (
    date        DATE NOT NULL REFERENCES dim_date(date),
    asset_class TEXT NOT NULL CHECK (asset_class IN ('EQUITY', 'RATES', 'FX')),
    series      TEXT NOT NULL,
    value       NUMERIC NOT NULL,
    PRIMARY KEY (date, series)
);

CREATE TABLE fact_valuations (
    date         DATE NOT NULL REFERENCES dim_date(date),
    trade_id     TEXT NOT NULL REFERENCES dim_trade(trade_id),
    market_value NUMERIC NOT NULL,
    pnl          NUMERIC NOT NULL,
    dv01         NUMERIC NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('LIVE', 'MATURED')),
    PRIMARY KEY (date, trade_id)
);

-- One row per load. Never dropped, so it keeps the history of every refresh.
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id            SERIAL      PRIMARY KEY,
    loaded_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    triggered_by      TEXT        NOT NULL,
    valuations_loaded INT         NOT NULL CHECK (valuations_loaded > 0)
);

-- Trades booked by visitors on the trade desk. Never dropped by a reload.
-- IDs start at T90001, so they can never collide with the official book (T00001-T00060).
CREATE SEQUENCE IF NOT EXISTS desk_trade_seq START 90001;
CREATE TABLE IF NOT EXISTS desk_trades (
    trade_id        TEXT        PRIMARY KEY DEFAULT ('T' || nextval('desk_trade_seq')),
    owner           TEXT        NOT NULL DEFAULT 'guest',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    trade_date      DATE        NOT NULL,
    desk            TEXT        NOT NULL CHECK (desk IN ('EQUITY', 'RATES', 'FX')),
    instrument_type TEXT        NOT NULL CHECK (instrument_type IN ('EQUITY_INDEX', 'BOND', 'FX_FORWARD')),
    underlying      TEXT        NOT NULL,
    direction       TEXT        NOT NULL CHECK (direction IN ('BUY', 'SELL')),
    quantity        BIGINT      NOT NULL CHECK (quantity > 0),
    trade_price     NUMERIC     NOT NULL CHECK (trade_price > 0),
    coupon_rate     NUMERIC,
    maturity_years  INT,
    spot_at_trade   NUMERIC,
    maturity_date   DATE,
    counterparty    TEXT        NOT NULL
);

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

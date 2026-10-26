-- One row per trade per day: the trade-level view behind the portfolio page
select
    valuation_date,
    trade_id,
    desk,
    instrument_type,
    underlying,
    direction,
    counterparty,
    market_value_usd,
    pnl_usd,
    dv01_usd,
    trade_status
from {{ ref('int_valuations_enriched') }}

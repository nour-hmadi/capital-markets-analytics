with valuations as (
    select * from {{ ref('stg_valuations') }}
),

trades as (
    select * from {{ ref('stg_trades') }}
),

enriched as (
    select
        v.valuation_date,
        v.trade_id,
        t.desk,
        t.instrument_type,
        t.underlying,
        t.direction,
        t.counterparty,
        t.trade_date,
        v.valuation_date - t.trade_date  as days_since_trade,
        v.market_value_usd,
        v.pnl_usd,
        v.dv01_usd,
        v.trade_status
    from valuations as v
    inner join trades as t
        on v.trade_id = t.trade_id
)

select * from enriched

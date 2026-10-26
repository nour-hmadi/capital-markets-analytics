-- The daily P&L mart must match the trade-level valuations on every date (to the cent).
-- Returns the dates that do NOT reconcile; zero rows means pass.
with mart as (
    select valuation_date, sum(pnl_usd) as pnl_usd
    from {{ ref('fct_daily_pnl_by_desk') }}
    group by valuation_date
),

source as (
    select valuation_date, sum(pnl_usd) as pnl_usd
    from {{ ref('stg_valuations') }}
    group by valuation_date
)

select
    coalesce(mart.valuation_date, source.valuation_date) as valuation_date,
    mart.pnl_usd   as mart_pnl_usd,
    source.pnl_usd as source_pnl_usd
from mart
full outer join source
    on mart.valuation_date = source.valuation_date
where mart.valuation_date is null
   or source.valuation_date is null
   or abs(mart.pnl_usd - source.pnl_usd) > 0.01

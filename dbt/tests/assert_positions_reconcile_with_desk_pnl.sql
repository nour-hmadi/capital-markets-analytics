-- The trade-level and desk-level marts must agree on total P&L every day (to the cent).
-- Returns the dates that do NOT agree; zero rows = pass.
with positions as (
    select valuation_date, sum(pnl_usd) as positions_pnl
    from {{ ref('fct_positions') }}
    group by valuation_date
),

desks as (
    select valuation_date, sum(pnl_usd) as desks_pnl
    from {{ ref('fct_daily_pnl_by_desk') }}
    group by valuation_date
)

select
    coalesce(p.valuation_date, d.valuation_date) as valuation_date,
    p.positions_pnl,
    d.desks_pnl
from positions as p
full outer join desks as d
    on p.valuation_date = d.valuation_date
where p.valuation_date is null
   or d.valuation_date is null
   or abs(p.positions_pnl - d.desks_pnl) > 0.01

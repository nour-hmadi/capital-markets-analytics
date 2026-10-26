-- Each desk must appear at most once per date in the daily P&L mart
select valuation_date, desk, count(*) as row_count
from {{ ref('fct_daily_pnl_by_desk') }}
group by valuation_date, desk
having count(*) > 1

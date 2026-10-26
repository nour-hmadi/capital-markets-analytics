-- Each trade appears at most once per date
select valuation_date, trade_id, count(*) as row_count
from {{ ref('fct_positions') }}
group by valuation_date, trade_id
having count(*) > 1

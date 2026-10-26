-- A day-on-day change must exist on every date except each series' first date.
-- Returns the rows that break this rule; zero rows = pass.
with numbered as (
    select
        series,
        price_date,
        daily_change,
        row_number() over (partition by series order by price_date) as day_number
    from {{ ref('fct_market_prices') }}
)

select *
from numbered
where (day_number = 1 and daily_change is not null)
   or (day_number > 1 and daily_change is null)

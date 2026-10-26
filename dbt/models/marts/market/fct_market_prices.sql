with prices as (
    select * from {{ ref('stg_market_prices') }}
),

with_changes as (
    select
        price_date,
        asset_class,
        series,
        value,
        value - lag(value) over by_series as daily_change,
        case when asset_class = 'RATES'
             then (value - lag(value) over by_series) * 100
        end as daily_change_bp,                 -- yields are in %, so x100 gives bp
        case when asset_class <> 'RATES'
             then value / lag(value) over by_series - 1
        end as daily_return                     -- prices: simple daily return
    from prices
    window by_series as (partition by series order by price_date)
)

select * from with_changes

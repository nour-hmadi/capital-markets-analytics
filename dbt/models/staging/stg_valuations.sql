with source as (
    select * from {{ source('raw', 'fact_valuations') }}
),

renamed as (
    select
        date                        as valuation_date,
        trade_id,
        market_value::numeric(18,2) as market_value_usd,
        pnl::numeric(18,2)          as pnl_usd,
        dv01::numeric(18,2)         as dv01_usd,
        status                      as trade_status
    from source
)

select * from renamed

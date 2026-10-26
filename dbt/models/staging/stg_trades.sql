with source as (
    select * from {{ source('raw', 'dim_trade') }}
),

renamed as (
    select
        trade_id,
        trade_date,
        desk,
        instrument_type,
        underlying,
        direction,
        case direction when 'BUY' then 1 when 'SELL' then -1 end as direction_sign,
        quantity::numeric       as quantity,
        trade_price::numeric    as trade_price,
        coupon_rate::numeric    as coupon_rate,
        maturity_years,
        spot_at_trade::numeric  as spot_at_trade,
        maturity_date,
        counterparty
    from source
)

select * from renamed

with source as (
    select * from {{ source('raw', 'fact_market_prices') }}
),

renamed as (
    select
        date            as price_date,
        asset_class,
        series,
        value::numeric  as value
    from source
)

select * from renamed	
	

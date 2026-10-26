{{
    config(
        materialized='incremental',
        unique_key=['valuation_date', 'desk'],
        incremental_strategy='delete+insert',
        on_schema_change='fail'
    )
}}

with enriched as (
    select * from {{ ref('int_valuations_enriched') }}
    {% if is_incremental() %}
    -- on later runs, only process dates newer than what the table already has
    where valuation_date > (select max(valuation_date) from {{ this }})
    {% endif %}
),

daily as (
    select
        valuation_date,
        desk,
        count(*)                               as trade_count,
        sum(market_value_usd)::numeric(18,2)   as market_value_usd,
        sum(pnl_usd)::numeric(18,2)            as pnl_usd,
        sum(dv01_usd)::numeric(18,2)           as dv01_usd
    from enriched
    group by valuation_date, desk
)

select * from daily

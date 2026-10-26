with bonds as (
    select * from {{ ref('int_valuations_enriched') }}
    where instrument_type = 'BOND'
),

by_security as (
    select
        valuation_date,
        underlying                                                    as security,
        count(*)                                                      as position_count,
        sum(dv01_usd)::numeric(18,2)                                  as dv01_usd,
        {{ rate_shock_pnl('sum(dv01_usd)', 10) }}::numeric(18,2)      as pnl_if_rates_up_10bp_usd
    from bonds
    group by valuation_date, underlying
)

select * from by_security

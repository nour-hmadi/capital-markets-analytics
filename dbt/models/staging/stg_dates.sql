with source as (
    select * from {{ source('raw', 'dim_date') }}
),

renamed as (
    select
        date as calendar_date,
        year,
        quarter,
        month,
        month_name,
        weekday
    from source
)

select * from renamed

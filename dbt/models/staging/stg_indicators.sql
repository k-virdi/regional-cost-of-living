-- Staging model: join facts to dimensions and pivot indicator types.
-- Produces one row per (region, month) with columns per indicator.

with base as (
    select
        r.country,
        r.province_state,
        r.city,
        d.full_date,
        d.year,
        d.month,
        d.is_recession,
        f.indicator_type,
        f.value,
        f.currency,
        f.is_inflation_adjusted
    from {{ source('warehouse', 'fct_indicators') }} f
    join {{ source('warehouse', 'dim_regions') }} r using (region_id)
    join {{ source('warehouse', 'dim_dates') }} d using (date_id)
)

select
    country,
    province_state,
    city,
    full_date,
    year,
    month,
    is_recession,
    max(case when indicator_type = 'cpi' then value end) as cpi,
    max(case when indicator_type = 'median_income' then value end) as median_income,
    max(case when indicator_type = 'average_rent' then value end) as average_rent,
    max(case when indicator_type = 'per_capita_income' then value end) as per_capita_income,
    max(case when indicator_type = 'unemployment_rate' then value end) as unemployment_rate,
    max(case when indicator_type = 'average_hourly_earnings' then value end) as avg_hourly_earnings
from base
group by 1, 2, 3, 4, 5, 6, 7

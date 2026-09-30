-- Affordability index: rent-to-income ratio and real income.
-- This is the core metric the dashboard and game theory layers consume.

with base as (
    select * from {{ ref('stg_indicators') }}
    where median_income is not null and average_rent is not null
)

select
    country,
    province_state,
    city,
    full_date,
    year,
    month,
    is_recession,
    median_income,
    average_rent,
    -- Annual rent-to-income ratio (monthly rent * 12 / annual income)
    round((average_rent * 12.0 / nullif(median_income, 0)) * 100, 2) as rent_to_income_pct,
    -- CPI-adjusted real median income (base year 2015 = 100)
    round(median_income / nullif(cpi, 0) * 100, 2) as real_median_income,
    -- Year-over-year rent growth
    round(
        (average_rent - lag(average_rent) over (
            partition by country, province_state, city order by full_date
        )) / nullif(lag(average_rent) over (
            partition by country, province_state, city order by full_date
        ), 0) * 100, 2
    ) as rent_yoy_pct
from base

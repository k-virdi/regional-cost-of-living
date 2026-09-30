-- Custom test: all indicator values must be positive.
select *
from {{ ref('stg_indicators') }}
where coalesce(cpi, 1) <= 0
   or coalesce(median_income, 1) <= 0
   or coalesce(average_rent, 1) <= 0

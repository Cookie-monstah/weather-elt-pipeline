{{ config(materialized='table') }}

select
    dl.location_id,
    dd.date_id,
    i.target_date,
    i.city,
    i.lead_time_hours,
    i.forecast_temperature,
    i.actual_avg_temperature,
    round((i.forecast_temperature - i.actual_avg_temperature)::numeric, 2) as temperature_error
from {{ ref('int_forecast_accuracy') }} i
join {{ ref('dim_location') }} dl on i.city = dl.city
join {{ ref('dim_date') }} dd on i.target_date = dd.date

{{ config(materialized='view') }}

select
    f.city,
    f.forecast_issued_at,
    f.target_time,
    date(f.target_time) as target_date,
    f.temperature as forecast_temperature,
    round(extract(epoch from (f.target_time - f.forecast_issued_at)) / 3600)::int as lead_time_hours,
    h.temp_max,
    h.temp_min,
    round(((h.temp_max + h.temp_min) / 2)::numeric, 2) as actual_avg_temperature
from {{ ref('stg_weather_forecast') }} f
join {{ ref('stg_weather_historical') }} h
    on f.city = h.city and date(f.target_time) = h.date

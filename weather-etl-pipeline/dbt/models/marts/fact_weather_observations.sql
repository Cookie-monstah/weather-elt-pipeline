{{ config(materialized='table') }}

with daily_actuals as (
    select * from {{ ref('stg_weather_historical') }}
),

daily_current_avg as (
    select * from {{ ref('int_daily_current_rollup') }}
)

select
    dl.location_id,
    dd.date_id,
    a.date,
    a.city,
    a.temp_max,
    a.temp_min,
    a.precipitation_sum,
    a.wind_speed_max,
    a.wind_direction_dominant,
    c.avg_temperature,
    c.avg_wind_speed,
    c.avg_humidity,
    c.avg_pressure
from daily_actuals a
left join daily_current_avg c
    on a.city = c.city and a.date = c.date
join {{ ref('dim_location') }} dl on a.city = dl.city
join {{ ref('dim_date') }} dd on a.date = dd.date

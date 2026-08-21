{{ config(materialized='view') }}

select
    city,
    date(observed_at) as date,
    round(avg(temperature)::numeric, 2) as avg_temperature,
    round(avg(wind_speed)::numeric, 2) as avg_wind_speed,
    round(avg(humidity)::numeric, 2) as avg_humidity,
    round(avg(pressure)::numeric, 2) as avg_pressure
from {{ ref('stg_weather_current') }}
group by
    city,
    date(observed_at)

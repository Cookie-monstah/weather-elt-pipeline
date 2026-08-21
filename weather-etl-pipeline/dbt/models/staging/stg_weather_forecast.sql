{{ config(materialized='table') }}

select
    id,
    city,
    country,
    latitude,
    longitude,
    forecast_issued_at,
    target_time,
    temperature,
    precipitation,
    wind_speed,
    wind_direction,
    humidity,
    pressure,
    weather_code,
    utc_offset_seconds,
    inserted_at
from {{ source('dev', 'raw_weather_forecast') }}

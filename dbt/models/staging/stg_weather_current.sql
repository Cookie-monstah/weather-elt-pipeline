{{ config(materialized='table') }}

with source as (
    select * from {{ source('dev', 'raw_weather_current') }}
),

de_dup as (
    select
        *,
        row_number() over (partition by city, observed_at order by inserted_at) as row_num
    from source
)

select
    id,
    city,
    country,
    latitude,
    longitude,
    observed_at,
    temperature,
    wind_speed,
    wind_direction,
    humidity,
    pressure,
    precipitation,
    weather_code,
    utc_offset_seconds,
    inserted_at
from de_dup
where row_num = 1

{{ config(materialized='table') }}

with source as (
    select * from {{ source('dev', 'raw_weather_historical') }}
),

de_dup as (
    select
        *,
        row_number() over (partition by city, date order by inserted_at desc) as row_num
    from source
)

select
    id,
    city,
    country,
    latitude,
    longitude,
    date,
    temp_max,
    temp_min,
    precipitation_sum,
    wind_speed_max,
    wind_direction_dominant,
    utc_offset_seconds,
    inserted_at
from de_dup
where row_num = 1

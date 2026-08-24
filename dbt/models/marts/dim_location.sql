{{ config(materialized='table') }}

with locations as (
    select city, country, latitude, longitude from {{ ref('stg_weather_current') }}
    union
    select city, country, latitude, longitude from {{ ref('stg_weather_forecast') }}
    union
    select city, country, latitude, longitude from {{ ref('stg_weather_historical') }}
),

deduped as (
    select distinct city, country, latitude, longitude
    from locations
)

select
    dense_rank() over (order by city) as location_id,
    city,
    country,
    latitude,
    longitude
from deduped

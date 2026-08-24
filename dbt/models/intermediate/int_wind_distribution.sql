{{ config(materialized='view') }}

with observations as (
    select city, wind_speed, wind_direction
    from {{ ref('stg_weather_current') }}
    where wind_direction is not null and wind_speed is not null
),

binned as (
    select
        city,
        wind_speed,
        mod(round(wind_direction / 22.5)::int, 16) as direction_index
    from observations
)

select
    city,
    direction_index,
    case direction_index
        when 0 then 'N' when 1 then 'NNE' when 2 then 'NE' when 3 then 'ENE'
        when 4 then 'E' when 5 then 'ESE' when 6 then 'SE' when 7 then 'SSE'
        when 8 then 'S' when 9 then 'SSW' when 10 then 'SW' when 11 then 'WSW'
        when 12 then 'W' when 13 then 'WNW' when 14 then 'NW' when 15 then 'NNW'
    end as direction,
    case
        when wind_speed < 5 then '0-5'
        when wind_speed < 10 then '5-10'
        when wind_speed < 15 then '10-15'
        when wind_speed < 20 then '15-20'
        else '20+'
    end as speed_bucket,
    count(*) as observation_count
from binned
group by city, direction_index, speed_bucket

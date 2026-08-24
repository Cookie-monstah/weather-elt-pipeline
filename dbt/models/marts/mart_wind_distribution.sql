{{ config(materialized='table') }}

select
    dl.location_id,
    w.city,
    w.direction_index,
    w.direction,
    w.speed_bucket,
    w.observation_count
from {{ ref('int_wind_distribution') }} w
join {{ ref('dim_location') }} dl on w.city = dl.city

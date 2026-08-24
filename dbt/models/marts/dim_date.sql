{{ config(materialized='table') }}

with bounds as (
    select
        min(date) as min_date,
        max(date) as max_date
    from {{ ref('stg_weather_historical') }}
),

spine as (
    select generate_series(
        (select min_date from bounds),
        (select max_date from bounds),
        interval '1 day'
    )::date as date
    where (select min_date from bounds) is not null
)

select
    to_char(date, 'YYYYMMDD')::int as date_id,
    date,
    extract(year from date)::int as year,
    extract(month from date)::int as month,
    extract(day from date)::int as day,
    extract(dow from date)::int as day_of_week,
    trim(to_char(date, 'Day')) as day_name,
    trim(to_char(date, 'Month')) as month_name
from spine

# weather-etl-pipeline

A local ETL pipeline that pulls current conditions, hourly forecasts, and
daily historical actuals from the [Open-Meteo](https://open-meteo.com/) API
(free, no API key required) for a configurable set of cities, loads them into
Postgres, transforms them with dbt into a star schema, orchestrates the run
with Airflow, and visualizes the results in Superset.

Because Open-Meteo exposes both forecasts and later-observed actuals, the
pipeline also builds a forecast-accuracy mart — comparing what was predicted
against what actually happened, broken out by lead time.

## Architecture

```
Open-Meteo API (geocoding, forecast, archive)
      │
      ▼
extraction/extract.py  ──▶  Postgres raw landing tables (append-only)
      │                       dev.raw_weather_current
      │                       dev.raw_weather_forecast
      │                       dev.raw_weather_historical
      ▼
  Airflow DAG
(dags/weather_etl_dag.py)
extract → dbt run → dbt test
                            │
                            ▼
                     dbt staging (clean/type/dedup)
                            │
                            ▼
                  dbt intermediate (rollups, forecast-vs-actual join)
                            │
                            ▼
                  dbt marts (star schema)
                     dim_location, dim_date
                     fact_weather_observations
                     fact_forecast_accuracy
                     mart_wind_distribution
                            │
                            ▼
                        Superset
                  ("Weather ETL Overview" dashboard)
```

- **extraction/** — for each configured city: geocodes it, pulls current
  conditions + next-48h hourly forecast in one call, and pulls one day of
  historical daily actuals (`HISTORICAL_BACKFILL_DAYS` days back). All three
  are appended to raw landing tables — nothing is overwritten, so staging
  models handle deduplication.
- **dags/** — Airflow DAG: run extraction for all cities, `dbt run`, then
  `dbt test`.
- **dbt/models/staging/** — 1:1 cleaned/typed/deduped views of each raw table.
- **dbt/models/intermediate/** — `int_daily_current_rollup` (daily avg
  temperature/wind/humidity/pressure from current-condition pulls),
  `int_forecast_accuracy` (joins each forecast row to the historical actual
  for its target date, computing lead time and error), `int_wind_distribution`
  (bins current-pull wind observations into 16-point compass directions ×
  speed buckets).
- **dbt/models/marts/** — star schema:
  - `dim_location` — city/country/lat/lon, one row per location
  - `dim_date` — calendar date spine derived from the historical data range
  - `fact_weather_observations` — daily grain: historical actuals
    (temp max/min, precipitation, max wind, dominant wind direction) plus
    same-day current-pull averages (temperature, wind speed, humidity,
    pressure), keyed by `location_id`/`date_id`
  - `fact_forecast_accuracy` — one row per forecast issuance/target hour,
    with `lead_time_hours` and `temperature_error` (forecast − actual)
  - `mart_wind_distribution` — observation counts per city/compass
    direction/speed bucket (wind-rose substitute, since Superset has no
    native wind-rose chart)
- **superset/dashboards/** — exported Superset dashboard definition
  (`.zip`) for version control — see [Dashboard](#dashboard) below.
- **postgres/** — init SQL that provisions the `airflow` and `superset`
  service databases alongside the main app database.
- **docker/** — Superset bootstrap/init scripts and `superset_config.py`.

## Prerequisites

- Docker and Docker Compose
- No API key needed (Open-Meteo is free and unauthenticated)

## Setup

1. Copy the environment template and adjust as needed (city list, backfill
   window, DB/Superset credentials):

   ```bash
   cp .env.example .env
   ```

2. Copy the dbt profile template (kept out of git since it's the file dbt
   actually reads):

   ```bash
   cp dbt/profiles.yml.example dbt/profiles.yml
   ```

3. Start the stack:

   ```bash
   docker compose up -d
   ```

4. Services:

   | Service  | URL                     | Notes                          |
   |----------|-------------------------|---------------------------------|
   | Airflow  | http://localhost:8000   | admin credentials printed on first `airflow standalone` boot |
   | Superset | http://localhost:8088   | admin / admin (change in production) |
   | Postgres | localhost:5000          | see `.env` for credentials     |

5. In the Airflow UI, unpause the `weather-etl-orchestrator` DAG. Each run:
   extracts current + forecast + one day of historical actuals for every city
   in `WEATHER_CITIES`, loads the raw tables, runs `dbt run`, then `dbt test`.

   Note: `fact_weather_observations` and `fact_forecast_accuracy` only
   populate once at least one day of historical actuals has landed —
   run the DAG a few times (or lower `HISTORICAL_BACKFILL_DAYS` cities'
   worth of days back) to build up enough history for forecast-accuracy
   comparisons to have matching actuals.

## Running extraction or dbt manually

```bash
# Extraction (from your host, with a local venv)
pip install -r extraction/requirements.txt
POSTGRES_HOST=localhost POSTGRES_PORT=5000 python extraction/extract.py

# dbt (inside the dbt container)
docker compose run --rm dbt run
docker compose run --rm dbt test
```

## Dashboard

The **"Weather ETL Overview"** dashboard (exported to
`superset/dashboards/`) has 6 charts, all cross-filterable by `city`:

| Chart | Type | Dataset | Notes |
|---|---|---|---|
| Daily Temperature by City | Line | `fact_weather_observations` | `temp_max`/`temp_min` over time, grouped by city, Time Grain = Day |
| Forecast Accuracy by Lead Time | Bar | `fact_forecast_accuracy` | `AVG(temperature_error)` by `lead_time_hours`, grouped by city — needs several days of history to populate |
| Precipitation Calendar Heatmap | Calendar Heatmap | `fact_weather_observations` | `SUM(precipitation_sum)`; Superset's Calendar Heatmap has no per-series groupby, so this is combined across cities (per-city split done via the dashboard's `city` filter) |
| Current Conditions Map | deck.gl Scatterplot | `geo_latest_conditions` (virtual/SQL dataset, see below) | Point size from `temp_max`; no basemap tiles unless `MAPBOX_API_KEY` is set |
| Extreme Heat Days by Month | Bar | `fact_weather_observations` | Custom SQL metric `COUNT(CASE WHEN temp_max > 30 THEN 1 END)` — tune the threshold per city's climate |
| Wind Direction & Speed Distribution | Bar (stacked) | `mart_wind_distribution` | `SUM(observation_count)` by `direction`, stacked by `speed_bucket` — wind-rose substitute |

**`geo_latest_conditions`** is a virtual dataset (saved from a SQL Lab query,
not a dbt model) since no single mart has both coordinates and metrics:

```sql
select
    dl.city, dl.country, dl.latitude, dl.longitude,
    f.date, f.temp_max, f.temp_min, f.avg_temperature, f.wind_direction_dominant
from dev.dim_location dl
join dev.fact_weather_observations f on dl.location_id = f.location_id
where f.date = (
    select max(date) from dev.fact_weather_observations f2
    where f2.location_id = f.location_id
)
```

To restore the dashboard on a fresh Superset instance: **Dashboards > Import
dashboard**, select the `.zip` in `superset/dashboards/`.

### Data volume caveat

Several charts (forecast accuracy, calendar heatmap, wind distribution,
extreme-heat tracker) are only interesting once the DAG has run repeatedly
over multiple days — with a single run they'll show sparse or empty results.
This is expected, not a bug; let the DAG accumulate history.

## Security notes

- No API key is required for this project since it uses Open-Meteo.
- `.env` and `dbt/profiles.yml` are gitignored — never commit real
  credentials. Only the `.example` templates are tracked.

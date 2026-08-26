import os
from datetime import date, timedelta

import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

WEATHER_CITIES = [
    c.strip() for c in os.environ.get("WEATHER_CITIES", "New York,London,Tokyo").split(",") if c.strip()
]
HISTORICAL_BACKFILL_DAYS = int(os.environ.get("HISTORICAL_BACKFILL_DAYS", "1"))

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

DB_CONFIG = {
    "host": os.environ.get("POSTGRES_HOST", "db"),
    "port": os.environ.get("POSTGRES_PORT", "5432"),
    "dbname": os.environ.get("POSTGRES_DB", "db"),
    "user": os.environ.get("POSTGRES_USER", "db_user"),
    "password": os.environ.get("POSTGRES_PASSWORD", "db_password"),
}


def geocode_city(city: str) -> dict:
    print(f"Geocoding {city}...")
    response = requests.get(GEOCODING_URL, params={"name": city, "count": 1}, timeout=10)
    response.raise_for_status()
    results = response.json().get("results")
    if not results:
        raise RuntimeError(f"No geocoding match found for city: {city}")
    result = results[0]
    return {
        "city": result["name"],
        "country": result.get("country", ""),
        "latitude": result["latitude"],
        "longitude": result["longitude"],
    }


def fetch_current_and_forecast(location: dict) -> tuple[dict, list[dict]]:
    print(f"Fetching current + hourly forecast for {location['city']}...")
    response = requests.get(
        FORECAST_URL,
        params={
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "current": "temperature_2m,wind_speed_10m,wind_direction_10m,relative_humidity_2m,"
            "surface_pressure,precipitation,weather_code",
            "hourly": "temperature_2m,precipitation,wind_speed_10m,wind_direction_10m,"
            "relative_humidity_2m,surface_pressure,weather_code",
            "forecast_days": 2,
            "timezone": "auto",
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    utc_offset_seconds = payload["utc_offset_seconds"]
    issued_at = payload["current"]["time"]

    current_record = {
        **location,
        "observed_at": issued_at,
        "temperature": payload["current"]["temperature_2m"],
        "wind_speed": payload["current"]["wind_speed_10m"],
        "wind_direction": payload["current"]["wind_direction_10m"],
        "humidity": payload["current"]["relative_humidity_2m"],
        "pressure": payload["current"]["surface_pressure"],
        "precipitation": payload["current"]["precipitation"],
        "weather_code": payload["current"]["weather_code"],
        "utc_offset_seconds": utc_offset_seconds,
    }

    hourly = payload["hourly"]
    forecast_records = [
        {
            **location,
            "forecast_issued_at": issued_at,
            "target_time": hourly["time"][i],
            "temperature": hourly["temperature_2m"][i],
            "precipitation": hourly["precipitation"][i],
            "wind_speed": hourly["wind_speed_10m"][i],
            "wind_direction": hourly["wind_direction_10m"][i],
            "humidity": hourly["relative_humidity_2m"][i],
            "pressure": hourly["surface_pressure"][i],
            "weather_code": hourly["weather_code"][i],
            "utc_offset_seconds": utc_offset_seconds,
        }
        for i in range(len(hourly["time"]))
    ]

    return current_record, forecast_records


def fetch_historical(location: dict, start_date: date, end_date: date) -> list[dict]:
    print(f"Fetching historical actuals for {location['city']} from {start_date} to {end_date}...")
    response = requests.get(
        ARCHIVE_URL,
        params={
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,"
            "wind_speed_10m_max,wind_direction_10m_dominant",
            "timezone": "auto",
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    daily = payload["daily"]
    utc_offset_seconds = payload["utc_offset_seconds"]

    return [
        {
            **location,
            "date": daily["time"][i],
            "temp_max": daily["temperature_2m_max"][i],
            "temp_min": daily["temperature_2m_min"][i],
            "precipitation_sum": daily["precipitation_sum"][i],
            "wind_speed_max": daily["wind_speed_10m_max"][i],
            "wind_direction_dominant": daily["wind_direction_10m_dominant"][i],
            "utc_offset_seconds": utc_offset_seconds,
        }
        for i in range(len(daily["time"]))
    ]


def connect_to_db():
    print("Connecting to the Postgres database...")
    return psycopg2.connect(**DB_CONFIG)


def create_tables(conn):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            CREATE SCHEMA IF NOT EXISTS dev;

            CREATE TABLE IF NOT EXISTS dev.raw_weather_current (
                id SERIAL PRIMARY KEY,
                city TEXT,
                country TEXT,
                latitude FLOAT,
                longitude FLOAT,
                observed_at TIMESTAMP,
                temperature FLOAT,
                wind_speed FLOAT,
                precipitation FLOAT,
                weather_code INT,
                utc_offset_seconds INT,
                inserted_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS dev.raw_weather_forecast (
                id SERIAL PRIMARY KEY,
                city TEXT,
                country TEXT,
                latitude FLOAT,
                longitude FLOAT,
                forecast_issued_at TIMESTAMP,
                target_time TIMESTAMP,
                temperature FLOAT,
                precipitation FLOAT,
                wind_speed FLOAT,
                weather_code INT,
                utc_offset_seconds INT,
                inserted_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS dev.raw_weather_historical (
                id SERIAL PRIMARY KEY,
                city TEXT,
                country TEXT,
                latitude FLOAT,
                longitude FLOAT,
                date DATE,
                temp_max FLOAT,
                temp_min FLOAT,
                precipitation_sum FLOAT,
                wind_speed_max FLOAT,
                utc_offset_seconds INT,
                inserted_at TIMESTAMP DEFAULT NOW()
            );

            ALTER TABLE dev.raw_weather_current
                ADD COLUMN IF NOT EXISTS wind_direction FLOAT,
                ADD COLUMN IF NOT EXISTS humidity FLOAT,
                ADD COLUMN IF NOT EXISTS pressure FLOAT;

            ALTER TABLE dev.raw_weather_forecast
                ADD COLUMN IF NOT EXISTS wind_direction FLOAT,
                ADD COLUMN IF NOT EXISTS humidity FLOAT,
                ADD COLUMN IF NOT EXISTS pressure FLOAT;

            ALTER TABLE dev.raw_weather_historical
                ADD COLUMN IF NOT EXISTS wind_direction_dominant FLOAT;
            """
        )
    conn.commit()


def insert_current(conn, record: dict):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO dev.raw_weather_current (
                city, country, latitude, longitude, observed_at,
                temperature, wind_speed, wind_direction, humidity, pressure,
                precipitation, weather_code, utc_offset_seconds
            ) VALUES (%(city)s, %(country)s, %(latitude)s, %(longitude)s, %(observed_at)s,
                      %(temperature)s, %(wind_speed)s, %(wind_direction)s, %(humidity)s, %(pressure)s,
                      %(precipitation)s, %(weather_code)s, %(utc_offset_seconds)s)
            """,
            record,
        )
    conn.commit()


def insert_forecast(conn, records: list[dict]):
    with conn.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO dev.raw_weather_forecast (
                city, country, latitude, longitude, forecast_issued_at, target_time,
                temperature, precipitation, wind_speed, wind_direction, humidity, pressure,
                weather_code, utc_offset_seconds
            ) VALUES (%(city)s, %(country)s, %(latitude)s, %(longitude)s, %(forecast_issued_at)s, %(target_time)s,
                      %(temperature)s, %(precipitation)s, %(wind_speed)s, %(wind_direction)s, %(humidity)s, %(pressure)s,
                      %(weather_code)s, %(utc_offset_seconds)s)
            """,
            records,
        )
    conn.commit()


def insert_historical(conn, records: list[dict]):
    with conn.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO dev.raw_weather_historical (
                city, country, latitude, longitude, date,
                temp_max, temp_min, precipitation_sum, wind_speed_max, wind_direction_dominant,
                utc_offset_seconds
            ) VALUES (%(city)s, %(country)s, %(latitude)s, %(longitude)s, %(date)s,
                      %(temp_max)s, %(temp_min)s, %(precipitation_sum)s, %(wind_speed_max)s, %(wind_direction_dominant)s,
                      %(utc_offset_seconds)s)
            """,
            records,
        )
    conn.commit()


def main():
    conn = connect_to_db()
    try:
        create_tables(conn)
        end_date = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=HISTORICAL_BACKFILL_DAYS - 1)

        for city in WEATHER_CITIES:
            location = geocode_city(city)

            current_record, forecast_records = fetch_current_and_forecast(location)
            insert_current(conn, current_record)
            insert_forecast(conn, forecast_records)
            print(f"Inserted 1 current + {len(forecast_records)} forecast rows for {location['city']}")

            historical_records = fetch_historical(location, start_date, end_date)
            insert_historical(conn, historical_records)
            print(f"Inserted {len(historical_records)} historical rows for {location['city']}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

sys.path.append("/opt/airflow/extraction")
from extract import main as run_extraction  # noqa: E402

default_args = {
    "description": "Fetch weather data from Open-Meteo, load raw records into "
    "Postgres, and transform them with dbt",
    "start_date": datetime(2024, 1, 1),
}

dag = DAG(
    dag_id="weather-etl-orchestrator",
    default_args=default_args,
    catchup=False,
    schedule=timedelta(hours=1),
)

DBT_MOUNTS = [
    Mount(
        source="/home/yow/repos/weather-etl-pipeline/dbt/models",
        target="/usr/app/models",
        type="bind",
    ),
    Mount(
        source="/home/yow/repos/weather-etl-pipeline/dbt/dbt_project.yml",
        target="/usr/app/dbt_project.yml",
        type="bind",
    ),
    Mount(
        source="/home/yow/repos/weather-etl-pipeline/dbt/profiles.yml",
        target="/root/.dbt/profiles.yml",
        type="bind",
    ),
]


def dbt_docker_operator(task_id: str, command: str) -> DockerOperator:
    return DockerOperator(
        task_id=task_id,
        image="ghcr.io/dbt-labs/dbt-postgres:1.9.latest",
        command=command,
        working_dir="/usr/app",
        mounts=DBT_MOUNTS,
        network_mode="weather-etl-pipeline_my-network",
        docker_url="unix://var/run/docker.sock",
        auto_remove="success",
    )


with dag:
    extract_and_load = PythonOperator(
        task_id="extract_and_load_task",
        python_callable=run_extraction,
    )

    transform = dbt_docker_operator("transform_data_task", "run")
    test = dbt_docker_operator("test_data_task", "test")

    extract_and_load >> transform >> test

import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

sys.path.append("/opt/airflow/extraction")
from extract import main as run_extraction  # noqa: E402

# Absolute path to this project on the Docker host, not inside this container.
# DockerOperator launches sibling containers via the host's Docker daemon, so
# bind-mount sources must be host paths. Set by docker-compose.yml from ${PWD}.
HOST_PROJECT_DIR = os.environ["HOST_PROJECT_DIR"]

default_args = {
    "description": "Fetch weather data from Open-Meteo, load raw records into "
    "Postgres, and transform them with dbt",
    "start_date": datetime(2024, 1, 1),
}

dag = DAG(
    dag_id="weather-elt-orchestrator",
    default_args=default_args,
    catchup=False,
    schedule=timedelta(hours=1),
)

DBT_MOUNTS = [
    Mount(
        source=f"{HOST_PROJECT_DIR}/dbt/models",
        target="/usr/app/models",
        type="bind",
    ),
    Mount(
        source=f"{HOST_PROJECT_DIR}/dbt/dbt_project.yml",
        target="/usr/app/dbt_project.yml",
        type="bind",
    ),
    Mount(
        source=f"{HOST_PROJECT_DIR}/dbt/profiles.yml",
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
        network_mode="weather-elt-pipeline_my-network",
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

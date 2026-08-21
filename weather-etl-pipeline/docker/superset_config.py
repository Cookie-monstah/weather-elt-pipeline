import os


def get_env_variable(var_name, default=None):
    try:
        return os.environ[var_name]
    except KeyError:
        if default is not None:
            return default
        raise EnvironmentError(f"The environment variable {var_name} was missing, abort...")


DATABASE_DIALECT = "postgresql+psycopg2"
DATABASE_USER = get_env_variable("SUPERSET_DB_USER")
DATABASE_PASSWORD = get_env_variable("SUPERSET_DB_PASSWORD")
DATABASE_HOST = get_env_variable("POSTGRES_HOST")
DATABASE_PORT = get_env_variable("POSTGRES_PORT")
DATABASE_DB = get_env_variable("SUPERSET_DB")

SQLALCHEMY_DATABASE_URI = (
    f"{DATABASE_DIALECT}://{DATABASE_USER}:{DATABASE_PASSWORD}"
    f"@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_DB}"
)

SECRET_KEY = get_env_variable("SUPERSET_SECRET_KEY")

from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from shared.config import settings


def _odbc_connection_string() -> str:
    params = {
        "DRIVER": f"{{{settings.db_driver}}}",
        "SERVER": settings.db_server,
        "DATABASE": settings.db_name,
        "UID": settings.db_user,
        "PWD": settings.db_password,
    }
    if "ODBC Driver" in settings.db_driver:
        # Driver 17+ defaults changed here (18 requires an explicit opt-out of
        # encryption to accept a local/self-signed cert); the legacy "SQL Server"
        # driver predates these keys and errors ("Invalid connection string
        # attribute") if they're present at all.
        params["Encrypt"] = "yes"
        params["TrustServerCertificate"] = "yes"
    return ";".join(f"{k}={v}" for k, v in params.items()) + ";"


def _build_engine() -> Engine:
    odbc_connect = quote_plus(_odbc_connection_string())
    return create_engine(f"mssql+pyodbc:///?odbc_connect={odbc_connect}")


engine: Engine = _build_engine()

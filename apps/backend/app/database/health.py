from typing import Literal

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.database.session import create_database_engine

DatabaseState = Literal["connected", "unavailable", "not_configured"]


def check_database(database_url: str | None, engine: Engine | None = None) -> DatabaseState:
    if not database_url and engine is None:
        return "not_configured"
    owns_engine = engine is None
    try:
        connection_engine = engine or create_database_engine(database_url)
        with connection_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "connected"
    except (SQLAlchemyError, OSError, ValueError):
        return "unavailable"
    finally:
        if owns_engine and "connection_engine" in locals():
            connection_engine.dispose()

from app.config import DB_SOURCES
from app.data.postgres_source import PostgresDataSource

_sources = {key: PostgresDataSource(cfg) for key, cfg in DB_SOURCES.items()}


def get_source(source_key: str = "default") -> PostgresDataSource:
    if source_key not in _sources:
        raise ValueError(f"Unknown source: {source_key}")
    return _sources[source_key]


def all_sources() -> dict:
    return _sources
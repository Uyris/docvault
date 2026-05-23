"""Settings: the provider-agnostic seam. Mostly URL normalisation logic."""

from __future__ import annotations

from app.core.config import Settings


def test_database_url_normalises_to_async_driver():
    s = Settings(database_url="postgres://u:p@host:5432/db")
    assert s.sqlalchemy_url == "postgresql+asyncpg://u:p@host:5432/db"


def test_database_url_postgresql_scheme_gets_async_driver():
    s = Settings(database_url="postgresql://u:p@host:5432/db")
    assert s.sqlalchemy_url == "postgresql+asyncpg://u:p@host:5432/db"


def test_database_url_assembled_from_parts_when_unset():
    s = Settings(
        database_url=None,
        postgres_user="docvault",
        postgres_password="secret",
        postgres_host="db",
        postgres_port=5432,
        postgres_db="docvault",
    )
    assert s.sqlalchemy_url == "postgresql+asyncpg://docvault:secret@db:5432/docvault"


def test_redis_dsn_default():
    s = Settings(redis_url=None, redis_host="cache", redis_port=6380)
    assert s.redis_dsn == "redis://cache:6380/0"


def test_cors_origins_parsed_to_list():
    s = Settings(cors_origins="http://a.com, http://b.com ,")
    assert s.cors_origin_list == ["http://a.com", "http://b.com"]


def test_max_upload_bytes():
    s = Settings(max_upload_mb=10)
    assert s.max_upload_bytes == 10 * 1024 * 1024

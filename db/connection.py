"""
Database connection pool management using asyncpg.
Provides a singleton pool for efficient connection reuse.
"""
import asyncio
from typing import Optional
from urllib.parse import quote

import asyncpg

from app.config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_SSLMODE,
)

_pool: Optional[asyncpg.Pool] = None
_pool_lock = asyncio.Lock()


def get_dsn() -> str:
    """Build PostgreSQL DSN from config."""
    user = quote(POSTGRES_USER, safe="")
    password = quote(POSTGRES_PASSWORD, safe="")
    db = quote(POSTGRES_DB, safe="")
    return f"postgresql://{user}:{password}@{POSTGRES_HOST}:{POSTGRES_PORT}/{db}?sslmode={POSTGRES_SSLMODE}"


async def get_pool() -> asyncpg.Pool:
    """Get or create the database connection pool."""
    global _pool
    if _pool is not None:
        return _pool
    
    async with _pool_lock:
        if _pool is not None:
            return _pool
        
        dsn = get_dsn()
        try:
            _pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=2,
                max_size=10,
                command_timeout=30,
            )
            print(f"[DB] Connection pool created: {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
        except Exception as e:
            print(f"[DB] Failed to create pool: {e}")
            raise
        
        return _pool


async def close_pool():
    """Close the database connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        print("[DB] Connection pool closed")


async def execute(query: str, *args) -> str:
    """Execute a query and return status."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)


async def fetch(query: str, *args) -> list:
    """Fetch multiple rows."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args) -> Optional[asyncpg.Record]:
    """Fetch a single row."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args):
    """Fetch a single value."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)

"""
Database connection management.
Uses PostgreSQL in production, SQLite fallback for local development.
"""
import asyncio
import os
import sqlite3
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import quote

from app.config import (
    DATABASE_URL,
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_SSLMODE,
    APP_ENV,
)

_pool = None
_pool_lock = asyncio.Lock()
_use_sqlite = False
_sqlite_path = Path(__file__).parent.parent / "data" / "signals.db"


def _is_local_dev() -> bool:
    """Check if we're in local development (no real DB available)."""
    # Allow SQLite fallback if PostgreSQL is disabled or in dev mode
    if DATABASE_URL and APP_ENV not in ("dev", "development"):
        return False
    if POSTGRES_HOST in ("disabled", "none", ""):
        return True
    if APP_ENV in ("dev", "development"):
        return True
    return POSTGRES_HOST in ("db", "localhost", "127.0.0.1")


def get_dsn() -> str:
    """Build PostgreSQL DSN from config."""
    if DATABASE_URL:
        # DigitalOcean typically provides DATABASE_URL. Normalize scheme for asyncpg.
        dsn = DATABASE_URL.strip()
        if dsn.startswith("postgres://"):
            dsn = "postgresql://" + dsn[len("postgres://"):]
        # If sslmode isn't specified, honor config default.
        if "sslmode=" not in dsn:
            joiner = "&" if "?" in dsn else "?"
            dsn = f"{dsn}{joiner}sslmode={POSTGRES_SSLMODE}"
        return dsn

    user = quote(POSTGRES_USER, safe="")
    password = quote(POSTGRES_PASSWORD, safe="")
    db = quote(POSTGRES_DB, safe="")
    return f"postgresql://{user}:{password}@{POSTGRES_HOST}:{POSTGRES_PORT}/{db}?sslmode={POSTGRES_SSLMODE}"


async def get_pool():
    """Get or create the database connection pool."""
    global _pool, _use_sqlite
    
    if _pool is not None:
        return _pool
    
    async with _pool_lock:
        if _pool is not None:
            return _pool
        
        # Try PostgreSQL first
        try:
            import asyncpg
            dsn = get_dsn()
            _pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=2,
                max_size=10,
                command_timeout=30,
            )
            # Avoid logging secrets. Prefer printing resolved host/db.
            try:
                from urllib.parse import urlparse

                p = urlparse(dsn)
                host = p.hostname or POSTGRES_HOST
                port = p.port or POSTGRES_PORT
                dbname = (p.path or "").lstrip("/") or POSTGRES_DB
                print(f"[DB] PostgreSQL pool created: {host}:{port}/{dbname}")
            except Exception:
                print(f"[DB] PostgreSQL pool created")
            return _pool
        except Exception as e:
            print(f"[DB] PostgreSQL unavailable: {e}")
            
            # Fallback to SQLite for local dev
            if _is_local_dev():
                _use_sqlite = True
                _sqlite_path.parent.mkdir(parents=True, exist_ok=True)
                _pool = sqlite3.connect(str(_sqlite_path), check_same_thread=False)
                _pool.row_factory = sqlite3.Row
                print(f"[DB] Using SQLite fallback: {_sqlite_path}")
                return _pool
            raise
        
        return _pool


async def close_pool():
    """Close the database connection pool."""
    global _pool, _use_sqlite
    if _pool is not None:
        if _use_sqlite:
            _pool.close()
        else:
            await _pool.close()
        _pool = None
        print("[DB] Connection closed")


def _convert_query_sqlite(query: str) -> str:
    """Convert PostgreSQL query syntax to SQLite."""
    # Convert $1, $2 placeholders to ?
    import re
    return re.sub(r'\$\d+', '?', query)


async def execute(query: str, *args) -> str:
    """Execute a query and return status."""
    global _use_sqlite
    pool = await get_pool()
    
    if _use_sqlite:
        try:
            cursor = pool.cursor()
            cursor.execute(_convert_query_sqlite(query), args)
            pool.commit()
            return "OK"
        except Exception as e:
            return str(e)
    else:
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)


async def fetch(query: str, *args) -> List[Any]:
    """Fetch multiple rows."""
    global _use_sqlite
    pool = await get_pool()
    
    if _use_sqlite:
        cursor = pool.cursor()
        cursor.execute(_convert_query_sqlite(query), args)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    else:
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)


async def fetchrow(query: str, *args) -> Optional[Any]:
    """Fetch a single row."""
    global _use_sqlite
    pool = await get_pool()
    
    if _use_sqlite:
        cursor = pool.cursor()
        cursor.execute(_convert_query_sqlite(query), args)
        row = cursor.fetchone()
        return dict(row) if row else None
    else:
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args):
    """Fetch a single value."""
    global _use_sqlite
    pool = await get_pool()
    
    if _use_sqlite:
        cursor = pool.cursor()
        cursor.execute(_convert_query_sqlite(query), args)
        row = cursor.fetchone()
        return row[0] if row else None
    else:
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *args)


def is_sqlite() -> bool:
    """Check if using SQLite fallback."""
    return _use_sqlite

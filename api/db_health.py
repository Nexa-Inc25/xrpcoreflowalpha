from fastapi import APIRouter
import asyncpg
from urllib.parse import quote
from app.config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_SSLMODE,
)

router = APIRouter()


@router.get("/health/db")
async def db_health():
    user = quote(POSTGRES_USER, safe="")
    password = quote(POSTGRES_PASSWORD, safe="")
    db = quote(POSTGRES_DB, safe="")
    dsn = (
        f"postgresql://{user}:{password}"
        f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{db}?sslmode={POSTGRES_SSLMODE}"
    )
    try:
        conn = await asyncpg.connect(dsn=dsn, timeout=3.0)
        try:
            val = await conn.fetchval("SELECT 1")
        finally:
            await conn.close()
        return {"status": "ok", "result": int(val)}
    except Exception:
        return {"status": "unreachable"}

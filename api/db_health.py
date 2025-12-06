from fastapi import APIRouter

router = APIRouter()


@router.get("/health/db")
async def db_health():
    """Check database health - works with both PostgreSQL and SQLite fallback."""
    try:
        from db.connection import fetchval, is_sqlite
        
        val = await fetchval("SELECT 1")
        db_type = "sqlite" if is_sqlite() else "postgresql"
        
        return {
            "status": "ok",
            "result": int(val) if val else 1,
            "type": db_type
        }
    except Exception as e:
        return {"status": "unreachable", "error": str(e)}

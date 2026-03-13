from fastapi import APIRouter
from sqlalchemy import text
from app.database import SessionLocal

router = APIRouter()

@router.get("/divergencias")
def ver_divergencias():

    db = SessionLocal()

    result = db.execute(text("""
        SELECT *
        FROM auditoria_estoque
        ORDER BY created_at DESC
        LIMIT 100
    """)).fetchall()

    db.close()

    return [dict(r._mapping) for r in result]

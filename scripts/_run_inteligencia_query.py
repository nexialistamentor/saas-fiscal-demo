"""One-off: run user SQL against DATABASE_URL (or sqlite fallback)."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SQL = """
SELECT id, empresa_id, created_at, impacto_financeiro_anual, restituicao_st, score_global, risco_tributario
FROM inteligencia_snapshots
ORDER BY created_at DESC
LIMIT 10;
"""


def main() -> int:
    url = os.getenv("DATABASE_URL", "sqlite:///./test.db")
    kwargs: dict = {"pool_pre_ping": True}
    if "sqlite" in url:
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # Railway/proxy: "require" pode falhar em alguns ambientes; prefer tenta SSL e recua se preciso.
        kwargs["connect_args"] = {"sslmode": os.getenv("PG_SSLMODE", "prefer")}

    try:
        engine = create_engine(url, **kwargs)
        with engine.connect() as conn:
            r = conn.execute(text(SQL))
            rows = r.fetchall()
            cols = list(r.keys())
    except Exception as e:
        print("ERRO:", e, file=sys.stderr)
        return 1

    print(" | ".join(cols))
    print("-" * min(140, 8 + sum(len(str(c)) for c in cols)))
    for row in rows:
        print(" | ".join(str(x) for x in row))
    print("Total:", len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

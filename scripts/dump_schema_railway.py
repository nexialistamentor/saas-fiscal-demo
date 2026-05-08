"""
Script de dump do schema PostgreSQL Railway.

Usa DATABASE_URL do ambiente — nunca hardcoded.
"""

import os
import sys

from sqlalchemy import create_engine, inspect

url = os.environ.get("DATABASE_URL")
if not url:
    print("ERRO: DATABASE_URL não definida")
    sys.exit(1)

engine = create_engine(url)
try:
    inspector = inspect(engine)
    for t in sorted(inspector.get_table_names()):
        print(f"-- {t}")
        for c in inspector.get_columns(t):
            print(f"  {c['name']}: {c['type']}")
        print()
    print("OK")
except Exception as e:
    print(f"ERRO: {e}")

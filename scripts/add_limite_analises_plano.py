"""
Script para adicionar coluna limite_analises na tabela planos (banco existente).
Execute: python scripts/add_limite_analises_plano.py
"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "..", "test.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()
try:
    cur.execute("PRAGMA table_info(planos)")
    cols = [c[1] for c in cur.fetchall()]
    if "limite_analises" not in cols:
        cur.execute("ALTER TABLE planos ADD COLUMN limite_analises INTEGER DEFAULT 100")
        conn.commit()
        print("Coluna limite_analises adicionada à tabela planos.")
        cur.execute("UPDATE planos SET limite_analises = 100 WHERE limite_analises IS NULL")
        cur.execute("UPDATE planos SET limite_analises = 2 WHERE nome = 'Teste'")
        conn.commit()
    else:
        print("Coluna limite_analises já existe.")
except Exception as e:
    conn.rollback()
    raise
finally:
    conn.close()

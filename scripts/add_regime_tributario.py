"""
Migração: adiciona coluna regime_tributario na tabela empresas.

Permite o fluxo BLOCO 10:
  empresa → regime_tributario → regime_router → engine tributário correto

Opção segura (não destrutiva). Execute:
  python -m scripts.add_regime_tributario

Alternativa em desenvolvimento: recriar o banco (excluir test.db e reiniciar a API).
"""
import sqlite3
import os

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "test.db"
)


def main():
    if not os.path.exists(DB_PATH):
        print(f"Banco não encontrado em {DB_PATH}. Ignorando migração.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(empresas)")
    colunas = [row[1] for row in cur.fetchall()]
    if "regime_tributario" in colunas:
        print("Coluna regime_tributario já existe.")
        conn.close()
        return

    cur.execute("ALTER TABLE empresas ADD COLUMN regime_tributario VARCHAR")
    conn.commit()
    conn.close()
    print("Coluna regime_tributario adicionada com sucesso.")


if __name__ == "__main__":
    main()

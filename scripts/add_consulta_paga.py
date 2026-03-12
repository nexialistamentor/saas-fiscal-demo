"""
Migração: adiciona coluna consulta_paga na tabela usuarios.
Execute: python -m scripts.add_consulta_paga
"""
import sqlite3
import os

# Caminho do banco (ajuste se necessário)
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

    # Verifica se a coluna já existe
    cur.execute("PRAGMA table_info(usuarios)")
    colunas = [row[1] for row in cur.fetchall()]
    if "consulta_paga" in colunas:
        print("Coluna consulta_paga já existe.")
        conn.close()
        return

    cur.execute("ALTER TABLE usuarios ADD COLUMN consulta_paga BOOLEAN DEFAULT 0")
    conn.commit()
    conn.close()
    print("Coluna consulta_paga adicionada com sucesso.")


if __name__ == "__main__":
    main()

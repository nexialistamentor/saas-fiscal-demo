"""
Migração: evoluir relatorios_analise com novos campos.
Executa uma única vez em bases existentes.

Novos campos: empresa_id, xml_chave, status, tempo_execucao, total_alertas, score_resultante
Novas FKs em engine_resultados e alertas_fiscais: relatorio_analise_id
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "test.db")


def coluna_existe(cursor, tabela: str, coluna: str) -> bool:
    cursor.execute(f"PRAGMA table_info({tabela})")
    return any(row[1] == coluna for row in cursor.fetchall())


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    colunas_relatorio = [
        ("empresa_id", "INTEGER REFERENCES empresas(id)"),
        ("xml_chave", "VARCHAR"),
        ("status", "VARCHAR"),
        ("tempo_execucao", "REAL"),
        ("total_alertas", "INTEGER"),
        ("score_resultante", "REAL"),
    ]
    for col, tipo in colunas_relatorio:
        if not coluna_existe(cursor, "relatorios_analise", col):
            cursor.execute(f"ALTER TABLE relatorios_analise ADD COLUMN {col} {tipo}")
            print(f"  + relatorios_analise.{col}")

    if not coluna_existe(cursor, "engine_resultados", "relatorio_analise_id"):
        cursor.execute(
            "ALTER TABLE engine_resultados ADD COLUMN relatorio_analise_id INTEGER REFERENCES relatorios_analise(id)"
        )
        print("  + engine_resultados.relatorio_analise_id")

    if not coluna_existe(cursor, "alertas_fiscais", "relatorio_analise_id"):
        cursor.execute(
            "ALTER TABLE alertas_fiscais ADD COLUMN relatorio_analise_id INTEGER REFERENCES relatorios_analise(id)"
        )
        print("  + alertas_fiscais.relatorio_analise_id")

    conn.commit()
    conn.close()
    print("Migração concluída.")


if __name__ == "__main__":
    main()

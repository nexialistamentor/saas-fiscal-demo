"""
Migração PostgreSQL (Railway): adiciona colunas faltantes.

Executa:
  - empresas.regime_tributario (usado pelo scheduler e engines fiscais)
  - usuarios.consulta_paga (usado para controle de consultas pagas)

Requer DATABASE_URL apontando para o PostgreSQL do Railway.

Uso:
  python -m scripts.run_railway_postgres_migration

Ou com DATABASE_URL explícito:
  set DATABASE_URL=postgresql://... && python -m scripts.run_railway_postgres_migration
"""
import os
import sys

# Carrega .env do diretório do projeto
try:
    from dotenv import load_dotenv
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(project_root, ".env"))
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL", "")


def main():
    if not DATABASE_URL or "sqlite" in DATABASE_URL:
        print("DATABASE_URL não configurado ou aponta para SQLite.")
        print("Configure DATABASE_URL com a URL do PostgreSQL do Railway e execute novamente.")
        print("Ex: set DATABASE_URL=postgresql://user:pass@host:port/railway")
        sys.exit(1)

    try:
        import psycopg2
        from urllib.parse import urlparse
    except ImportError as e:
        print(f"Dependência ausente: {e}")
        sys.exit(1)

    # Railway às vezes usa postgres://; psycopg2 espera postgresql://
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = "postgresql://" + url[10:]
    # Railway exige SSL; adiciona sslmode se não estiver presente
    if "sslmode=" not in url and "?" not in url:
        url += "?sslmode=require"
    elif "sslmode=" not in url:
        url += "&sslmode=require"

    try:
        conn = psycopg2.connect(url)
        conn.autocommit = True
        cur = conn.cursor()

        # empresas.regime_tributario (PostgreSQL 9.6+ suporta IF NOT EXISTS)
        cur.execute("""
            ALTER TABLE empresas
            ADD COLUMN IF NOT EXISTS regime_tributario VARCHAR(50);
        """)
        print("✓ Coluna empresas.regime_tributario OK")

        # usuarios.consulta_paga (evita erro se já existir)
        cur.execute("""
            ALTER TABLE usuarios
            ADD COLUMN IF NOT EXISTS consulta_paga BOOLEAN DEFAULT FALSE;
        """)
        print("✓ Coluna usuarios.consulta_paga OK")

        cur.close()
        conn.close()
        print("\nMigração aplicada com sucesso no PostgreSQL.")
    except Exception as e:
        print(f"Erro ao aplicar migração: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

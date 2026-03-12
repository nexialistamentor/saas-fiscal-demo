"""
Cria as tabelas do banco de dados (documentos_fiscais, itens_fiscais, etc.).

Use quando as tabelas ainda não existirem (ex.: primeiro deploy no Railway).

Uso no PowerShell:
  python scripts/init_db.py

Ou:
  python -m scripts.init_db

Requer DATABASE_URL configurado (ex.: no .env ou variável de ambiente).
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

# Garante que o projeto está no path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def main():
    from app.database import engine
    from app import models

    models.Base.metadata.create_all(bind=engine)
    print("✓ Tabelas criadas com sucesso (documentos_fiscais, itens_fiscais, etc.)")
    print("  Atualize a página no Railway → Postgres → Banco de dados para conferir.")


if __name__ == "__main__":
    main()

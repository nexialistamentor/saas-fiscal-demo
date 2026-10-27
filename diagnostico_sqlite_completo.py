"""
Diagnostico completo: tenta criar CADA tabela do schema real
individualmente contra uma base SQLite temporaria em memoria, sem
parar na primeira falha -- ao contrario de create_all(), que para
na primeira tabela problematica.

Nao escreve em app/database.py nem em nenhum ficheiro do repo.
So le os modelos e testa contra uma engine sqlite:///:memory: isolada.

Uso (a partir da raiz do repo, com o patch v3 ja aplicado ou nao --
funciona em qualquer estado):
    python diagnostico_sqlite_completo.py
"""
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from app import models

engine_teste = create_engine("sqlite:///:memory:")

tabelas = models.Base.metadata.sorted_tables
falhas = []
ok = []

for tabela in tabelas:
    try:
        tabela.create(bind=engine_teste, checkfirst=False)
        ok.append(tabela.name)
    except OperationalError as e:
        falhas.append((tabela.name, str(e).splitlines()[0]))
    except Exception as e:
        falhas.append((tabela.name, f"{type(e).__name__}: {e}"))

print(f"\n=== {len(ok)} tabelas OK, {len(falhas)} tabelas com falha ===\n")

if falhas:
    print("TABELAS COM FALHA:")
    for nome, erro in falhas:
        print(f"  - {nome}: {erro}")
else:
    print("Nenhuma falha -- schema inteiro compativel com SQLite.")

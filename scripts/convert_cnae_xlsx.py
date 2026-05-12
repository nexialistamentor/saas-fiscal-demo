"""
Script soberano de conversão CNAE XLSX → CSV.

Uso:
    python scripts/convert_cnae_xlsx.py

Fonte: IBGE/Concla — CNAE Subclasses (versão detectada automaticamente)
Output: data/cnae/cnae_subclasses.csv (UTF-8, sempre substituído)

Princípio: dados oficiais versionados no repo — sem dependência de API em runtime.
"""

import csv
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("ERRO: pip install openpyxl")
    sys.exit(1)

XLSX_PATH = Path("data/cnae/CNAE_Subclasses_2_3_Estrutura_Detalhada.xlsx")
CSV_PATH = Path("data/cnae/cnae_subclasses.csv")
SHEET_NAME = "Estrutura Det. CNAE Subclass2.3"
HEADER_ROWS = 4  # linhas a ignorar antes dos dados


def converter():
    print(f"A ler: {XLSX_PATH}")
    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
    ws = wb[SHEET_NAME]

    # Estado hierárquico — forward fill por nível
    secao = divisao = grupo = classe = ""
    subclasses = []

    for row in ws.iter_rows(min_row=HEADER_ROWS + 1, values_only=True):
        col_secao, col_divisao, col_grupo, col_classe, col_subclasse, col_nome = (
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
        )

        # Actualiza estado hierárquico
        if col_secao:
            secao = str(col_secao).strip()
            continue  # linha de secção — não é subclasse
        if col_divisao:
            divisao = str(col_divisao).strip()
            continue
        if col_grupo:
            grupo = str(col_grupo).strip()
            continue
        if col_classe:
            classe = str(col_classe).strip()
            continue
        if col_subclasse and col_nome:
            subclasses.append(
                {
                    "codigo_subclasse": str(col_subclasse).strip(),
                    "descricao": str(col_nome).strip(),
                    "codigo_classe": classe,
                    "codigo_grupo": grupo,
                    "codigo_divisao": divisao,
                    "secao": secao,
                    "versao_cnae": "2.3",
                }
            )

    wb.close()

    # Escreve CSV UTF-8
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "codigo_subclasse",
                "descricao",
                "codigo_classe",
                "codigo_grupo",
                "codigo_divisao",
                "secao",
                "versao_cnae",
            ],
        )
        writer.writeheader()
        writer.writerows(subclasses)

    print(f"[OK] {len(subclasses)} subclasses exportadas -> {CSV_PATH}")
    return len(subclasses)


if __name__ == "__main__":
    total = converter()
    # Validação soberana — CNAE 2.3 deve ter mais de 1300 subclasses
    if total < 1300:
        print(f"AVISO: total inesperado ({total}). Verificar estrutura do XLSX.")
        sys.exit(1)
    print("[OK] Validacao passou.")

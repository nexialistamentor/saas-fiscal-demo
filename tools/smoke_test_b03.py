"""
smoke_test_b03.py

Teste de fumo (nao pytest, script standalone): liga confrontar_xml_b03 a
uma sessao de DB real e ao XML sintetico do B02 R6 ja existente em
tests/fixtures/. Primeiro teste de B03 contra dados reais do repositorio,
nao mocks.

Uso (a partir da raiz do repo):
    python tools\\smoke_test_b03.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.services.enterprise_b03_item_reconciliation import confrontar_xml_b03


def main():
    xml_path = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "b02_r6_synthetic_nfeproc_20261105.xml"
    if not xml_path.is_file():
        print(f"ERRO: fixture nao encontrada em {xml_path}")
        sys.exit(1)

    xml_bytes = xml_path.read_bytes()

    db = SessionLocal()
    try:
        resultado = confrontar_xml_b03(db=db, xml_bytes=xml_bytes)
    finally:
        db.close()

    print("estado:", resultado.get("estado"))
    print("autoridade_fiscal:", resultado.get("autoridade_fiscal"))
    print("chave_nfe:", resultado.get("chave_nfe"))
    print("uf_operacao:", resultado.get("uf_operacao"))
    print("blocos_normativos:", json.dumps(resultado.get("blocos_normativos", []), indent=2, ensure_ascii=False))
    bruto = resultado.get("resultado_bruto", {})
    print("resultado_bruto.estado:", bruto.get("estado"))
    print("resultado_bruto.motivo:", bruto.get("motivo"))
    print("divergencias:", json.dumps(bruto.get("divergencias", []), indent=2, ensure_ascii=False))
    print("motivos_pendentes:", bruto.get("motivos_pendentes"))


if __name__ == "__main__":
    main()

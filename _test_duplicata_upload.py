"""
Teste P0.1 — Validação de deduplicação no /upload-xml

Cenário:
  1º upload do mesmo XML → sucesso (200) com documento_id
  2º upload do mesmo XML → 409 Conflict com chave_nfe + documento_id
"""
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///./test_duplicata.db"
os.environ["ENVIRONMENT"] = "development"

if os.path.exists("test_duplicata.db"):
    os.remove("test_duplicata.db")

from starlette.testclient import TestClient
from app.main import app
from app.database import engine
from app import models

models.Base.metadata.create_all(bind=engine)

client = TestClient(app)

SEP = "=" * 60
XML_PATH = "app/xmls_testes/xml_teste.xml"


def setup_user_and_token():
    """Cria plano, regista utilizador, faz login, retorna headers com token."""

    from app.database import SessionLocal
    db = SessionLocal()

    plano = db.query(models.Plano).filter(models.Plano.nome == "Basico").first()
    if not plano:
        plano = models.Plano(nome="Basico", limite_cnpjs=5, limite_analises=100)
        db.add(plano)
        db.commit()
        db.refresh(plano)
    db.close()

    r = client.post("/auth/register", json={
        "email": "teste_dup@fiscal.com",
        "password": "SenhaForte123!",
    })
    assert r.status_code == 200, f"Register falhou: {r.status_code} — {r.text}"

    r = client.post("/auth/login", data={
        "username": "teste_dup@fiscal.com",
        "password": "SenhaForte123!",
    })
    assert r.status_code == 200, f"Login falhou: {r.status_code} — {r.text}"
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def upload_xml(headers: dict):
    """Envia o XML de teste via /upload-xml."""
    with open(XML_PATH, "rb") as f:
        return client.post(
            "/upload-xml",
            headers=headers,
            files={"file": ("xml_teste.xml", f, "application/xml")},
        )


def main():
    print(SEP)
    print("  TESTE P0.1 — DEDUPLICAÇÃO /upload-xml")
    print(SEP)

    headers = setup_user_and_token()
    print("[OK] Utilizador criado e autenticado\n")

    # ── 1º upload: deve ter sucesso ──
    print("1º upload (mesmo XML)...")
    r1 = upload_xml(headers)
    print(f"   Status: {r1.status_code}")
    print(f"   Body:   {r1.json()}")

    ok_1 = r1.status_code == 200 and "documento_id" in r1.json()
    doc_id_1 = r1.json().get("documento_id")
    print(f"   {'[OK]' if ok_1 else '[FALHA]'} 1º upload → {r1.status_code}"
          f" documento_id={doc_id_1}\n")

    # ── 2º upload: deve dar 409 ──
    print("2º upload (mesmo XML — duplicata)...")
    r2 = upload_xml(headers)
    print(f"   Status: {r2.status_code}")
    print(f"   Body:   {r2.json()}")

    body2 = r2.json()
    detail = body2.get("detail", {})
    ok_2 = (
        r2.status_code == 409
        and isinstance(detail, dict)
        and "chave_nfe" in detail
        and "documento_id" in detail
    )
    print(f"   {'[OK]' if ok_2 else '[FALHA]'} 2º upload → {r2.status_code}")
    if ok_2:
        print(f"   chave_nfe     = {detail['chave_nfe']}")
        print(f"   documento_id  = {detail['documento_id']}")
        print(f"   Ref. cruzada: doc_id original ({doc_id_1}) == detalhe ({detail['documento_id']}):"
              f" {'SIM' if doc_id_1 == detail['documento_id'] else 'NÃO'}")

    # ── Veredicto ──
    print(f"\n{SEP}")
    if ok_1 and ok_2:
        print("  RESULTADO: PASSOU — Deduplicação funciona corretamente")
        print("    1º upload → 200 + documento_id")
        print("    2º upload → 409 + chave_nfe + documento_id")
    else:
        print("  RESULTADO: FALHOU")
        if not ok_1:
            print(f"    1º upload esperava 200, obteve {r1.status_code}")
        if not ok_2:
            print(f"    2º upload esperava 409 c/ chave_nfe+documento_id, obteve {r2.status_code}")
    print(SEP)

    # Limpeza (fechar engine antes de apagar no Windows)
    try:
        engine.dispose()
        if os.path.exists("test_duplicata.db"):
            os.remove("test_duplicata.db")
    except OSError:
        pass

    return 0 if (ok_1 and ok_2) else 1


if __name__ == "__main__":
    sys.exit(main())

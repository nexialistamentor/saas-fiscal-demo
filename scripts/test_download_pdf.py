"""
Valida o download do relatório PDF (endpoint POST /relatorio/gerar).
Uso: python -m scripts.test_download_pdf
Requer: backend rodando em http://127.0.0.1:8000 e usuário com consulta_paga.
"""
import sys
from pathlib import Path

# raiz do projeto
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Token do frontend (teste@empresa.com)
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0ZUBlbXByZXNhLmNvbSIsImV4cCI6MTc3MzY5MDk0N30.08LTOrbSFlPp8FOna3qW0ekxVUJlxjELmiTWs6y6WRA"
BASE = "http://127.0.0.1:8000"
# idPerfil usado no dashboard (empresa)
PERFIL_ID = 4


def main():
    try:
        import urllib.request
        import urllib.error
        import json
    except ImportError:
        print("Use Python com urllib (padrão).")
        return

    url = f"{BASE}/relatorio/gerar"
    data = json.dumps({"perfil_id": PERFIL_ID}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TOKEN}",
        },
    )

    out_path = ROOT / "relatorio-fiscal-teste.pdf"
    print(f"Chamando POST {url} com perfil_id={PERFIL_ID} ...")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            content_type = resp.headers.get("Content-Type", "")
            if "application/pdf" in content_type and len(content) > 100:
                out_path.write_bytes(content)
                print(f"OK: PDF gerado ({len(content)} bytes) -> {out_path}")
            else:
                print(f"Resposta inesperada: Content-Type={content_type}, len={len(content)}")
                out_path.write_bytes(content)
                print(f"Salvo em {out_path} para inspeção.")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Erro HTTP {e.code}: {e.reason}")
        print(f"Body: {body[:500]}")
        if e.code == 402:
            print("\n--> Libere a consulta: GET http://127.0.0.1:8000/admin/liberar-consulta?email=teste@empresa.com")
    except Exception as e:
        print(f"Erro: {e}")


if __name__ == "__main__":
    main()

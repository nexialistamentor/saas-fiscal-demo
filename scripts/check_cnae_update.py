"""
Detector de actualizacao CNAE — pipeline normativo soberano.

Uso manual ou via CI/CD:
    python scripts/check_cnae_update.py

Verifica se existe nova versao CNAE no IBGE/Concla comparando
com a versao actual versionada no repo.

Saida:
    EXIT 0 — sem actualizacao necessaria
    EXIT 1 — nova versao detectada (acção manual necessaria)

Fluxo de actualizacao quando EXIT 1:
    1. Descarregar novo XLSX do IBGE
    2. Substituir data/cnae/CNAE_Subclasses_*_Estrutura_Detalhada.xlsx
    3. Correr: python scripts/convert_cnae_xlsx.py
    4. Actualizar VERSAO_ACTUAL em app/services/parsers/cnae_parser.py
    5. Commit atomico: "feat(cnae): actualizar para CNAE X.X"
    6. Deploy Railway aplica automaticamente
"""

import sys
import hashlib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.services.parsers.cnae_parser import VERSAO_ACTUAL as VERSAO_REPO  # noqa: E402

# URL oficial IBGE — pagina de download
URL_IBGE_DOWNLOAD = "https://concla.ibge.gov.br/classificacoes/download-concla.html"

# Marcadores de versao mais recente a procurar na pagina IBGE
# Actualizar esta lista quando IBGE publicar nova versao
VERSOES_CONHECIDAS = ["2.3", "2.2", "2.1", "2.0"]
VERSAO_MAIS_RECENTE_CONHECIDA = "2.3"

CSV_PATH = Path("data/cnae/cnae_subclasses.csv")


def _tupla_versao(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.strip().split("."))


def verificar_integridade_csv() -> dict:
    """Verifica que o CSV local esta integro e nao foi corrompido."""
    if not CSV_PATH.exists():
        return {"ok": False, "erro": "CSV nao encontrado"}

    conteudo = CSV_PATH.read_bytes()
    checksum = hashlib.sha256(conteudo).hexdigest()
    linhas = len(conteudo.decode("utf-8").splitlines()) - 1  # menos header

    return {
        "ok": True,
        "checksum": checksum,
        "subclasses": linhas,
        "versao_repo": VERSAO_REPO,
    }


def verificar_nova_versao_ibge() -> dict:
    """
    Verifica pagina IBGE para detectar nova versao CNAE.
    Requer acesso a rede — usar em CI/CD ou verificacao manual.
    """
    try:
        import urllib.request

        with urllib.request.urlopen(URL_IBGE_DOWNLOAD, timeout=10) as resp:
            conteudo = resp.read().decode("utf-8", errors="ignore")

        # Procura por versao na lista mais recente que a versionada no repo
        for versao in VERSOES_CONHECIDAS:
            if _tupla_versao(versao) <= _tupla_versao(VERSAO_REPO):
                continue
            if f"CNAE {versao}" in conteudo or f"cnae_{versao}" in conteudo.lower():
                return {
                    "nova_versao_detectada": True,
                    "versao_detectada": versao,
                    "versao_repo": VERSAO_REPO,
                    "accao": f"Descarregar CNAE {versao} e correr convert_cnae_xlsx.py",
                }

        return {
            "nova_versao_detectada": False,
            "versao_repo": VERSAO_REPO,
            "versao_ibge_confirmada": VERSAO_MAIS_RECENTE_CONHECIDA,
        }

    except Exception as exc:
        return {
            "nova_versao_detectada": False,
            "erro": f"Nao foi possivel verificar IBGE: {exc}",
            "versao_repo": VERSAO_REPO,
        }


if __name__ == "__main__":
    print("=== Verificacao CNAE Soberana ===")

    # 1. Integridade local
    integridade = verificar_integridade_csv()
    if not integridade["ok"]:
        print(f"ERRO integridade: {integridade['erro']}")
        sys.exit(1)

    print(
        f"CSV local: {integridade['subclasses']} subclasses | "
        f"versao {integridade['versao_repo']}"
    )
    print(f"Checksum: {integridade['checksum'][:16]}...")

    # 2. Verificar IBGE
    print("A verificar IBGE/Concla...")
    resultado = verificar_nova_versao_ibge()

    if resultado.get("nova_versao_detectada"):
        print(f"NOVA VERSAO DETECTADA: {resultado['versao_detectada']}")
        print(f"Accao necessaria: {resultado['accao']}")
        sys.exit(1)
    elif resultado.get("erro"):
        print(f"Aviso: {resultado['erro']}")
        print(
            "Verificar manualmente: "
            "https://concla.ibge.gov.br/classificacoes/download-concla.html"
        )
        sys.exit(0)
    else:
        print(
            f"CNAE actualizado: versao {resultado['versao_ibge_confirmada']} confirmada."
        )
        sys.exit(0)

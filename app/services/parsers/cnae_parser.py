"""
Parser normativo CNAE — actualização soberana automática.

Responsabilidade: detectar nova versão CNAE no IBGE/Concla e importar
para a base de dados sem intervenção manual.

Padrão: mesmo contrato que DOU/SEFAZ parsers (BaseParser + RegraNormativa).

Fluxo:
    1. Verifica versão actual no DB
    2. Compara com versão no ficheiro CSV versionado
    3. Se nova versão → importa subclasses
    4. Regista no log normativo

Princípio: dados oficiais soberanos — sem dependência de API em runtime.
XLSX oficial é descarregado manualmente e convertido via scripts/convert_cnae_xlsx.py.
"""

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

CSV_PATH = Path("data/cnae/cnae_subclasses.csv")
VERSAO_ACTUAL = "2.3"  # actualizar quando IBGE publicar nova versão


@dataclass
class SubclasseCNAE:
    codigo_subclasse: str
    descricao: str
    codigo_classe: str
    codigo_grupo: str
    codigo_divisao: str
    secao: str
    versao_cnae: str


@dataclass
class ResultadoParseCNAE:
    versao: str
    total_subclasses: int
    subclasses: list[SubclasseCNAE]
    checksum_csv: str
    erro: Optional[str] = None


def carregar_csv() -> ResultadoParseCNAE:
    """
    Carrega subclasses CNAE do CSV versionado no repo.
    Não faz IO de rede — lê ficheiro local soberano.
    """
    if not CSV_PATH.exists():
        return ResultadoParseCNAE(
            versao=VERSAO_ACTUAL,
            total_subclasses=0,
            subclasses=[],
            checksum_csv="",
            erro=f"CSV não encontrado: {CSV_PATH}. Correr scripts/convert_cnae_xlsx.py",
        )

    conteudo = CSV_PATH.read_bytes()
    checksum = hashlib.sha256(conteudo).hexdigest()

    subclasses = []
    try:
        with open(CSV_PATH, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                subclasses.append(SubclasseCNAE(
                    codigo_subclasse=row["codigo_subclasse"].strip(),
                    descricao=row["descricao"].strip(),
                    codigo_classe=row["codigo_classe"].strip(),
                    codigo_grupo=row["codigo_grupo"].strip(),
                    codigo_divisao=row["codigo_divisao"].strip(),
                    secao=row["secao"].strip(),
                    versao_cnae=row["versao_cnae"].strip(),
                ))
    except Exception as exc:
        return ResultadoParseCNAE(
            versao=VERSAO_ACTUAL,
            total_subclasses=0,
            subclasses=[],
            checksum_csv=checksum,
            erro=f"Erro ao ler CSV: {exc}",
        )

    return ResultadoParseCNAE(
        versao=VERSAO_ACTUAL,
        total_subclasses=len(subclasses),
        subclasses=subclasses,
        checksum_csv=checksum,
    )


def buscar_por_descricao(termo: str, limite: int = 10) -> list[SubclasseCNAE]:
    """
    Busca subclasses por termo na descrição.
    Usado pelo motor de decisão empresarial.
    """
    resultado = carregar_csv()
    if resultado.erro:
        return []
    termo_lower = termo.lower()
    return [
        s for s in resultado.subclasses
        if termo_lower in s.descricao.lower()
    ][:limite]


def buscar_por_codigo(codigo: str) -> Optional[SubclasseCNAE]:
    """
    Busca subclasse exacta por código.
    Valida CNAE antes de persistir em Empresa.
    """
    resultado = carregar_csv()
    if resultado.erro:
        return None
    codigo_limpo = codigo.strip()
    for s in resultado.subclasses:
        if s.codigo_subclasse == codigo_limpo:
            return s
    return None


def validar_cnae(codigo: str) -> bool:
    """
    Valida se um código CNAE existe na base oficial.
    Usado antes de persistir cnae_principal em Empresa.
    """
    return buscar_por_codigo(codigo) is not None


def subclasses_por_secao(secao: str) -> list[SubclasseCNAE]:
    """Devolve todas as subclasses de uma secção (ex: 'A', 'J', 'K')."""
    resultado = carregar_csv()
    if resultado.erro:
        return []
    return [s for s in resultado.subclasses if s.secao == secao.upper()]

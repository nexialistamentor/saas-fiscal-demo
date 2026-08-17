"""Extrator determinístico do snapshot oficial do Anexo XI do MEI.

Este módulo apenas devolve dados em memória; não escreve artefactos derivados.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pdfplumber


SHA256_OFICIAL = "CB3845804F3C14CB9CB1320AEE19BF14498CF15988CD9263FD4618D8FAAAB8B6"
TOTAL_PAGINAS = 43
CONTAGENS_ESPERADAS = {"A": 467, "B": 4}
CNAE_RE = re.compile(r"^\d{4}-\d/\d{2}$")


class AnexoXIExtractionError(ValueError):
    """Indica que a fonte ou a extração violou o contrato fechado."""


@dataclass(frozen=True)
class RegistroAnexoXI:
    tabela: str
    ocupacao: str
    cnae: str
    descricao_subclasse_cnae: str
    iss: bool
    icms: bool
    pagina_fonte: int


@dataclass(frozen=True)
class ResultadoExtracao:
    registros: tuple[RegistroAnexoXI, ...]
    paginas: int
    recomposicoes: int
    anomalias: tuple[str, ...]
    duplicados: tuple[tuple[str, str, str], ...]


def _normalizar(valor: object) -> str:
    texto = "" if valor is None else str(valor)
    return " ".join(unicodedata.normalize("NFKC", texto).split()).strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fonte:
        for bloco in iter(lambda: fonte.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest().upper()


def _e_cabecalho(colunas: list[str]) -> bool:
    """Reconhece o cabeçalho pelas três colunas estruturais inequívocas."""
    return len(colunas) == 5 and colunas[1] == "CNAE" and colunas[3:] == ["ISS", "ICMS"]


def extract_anexo_xi(path: str | Path) -> ResultadoExtracao:
    """Extrai e valida integralmente o snapshot, sem produzir ficheiros."""
    fonte = Path(path)
    hash_obtido = _sha256(fonte)
    if hash_obtido != SHA256_OFICIAL:
        raise AnexoXIExtractionError(
            f"SHA-256 divergente: esperado {SHA256_OFICIAL}, obtido {hash_obtido}"
        )

    registros_brutos: list[tuple[str, list[str], int]] = []
    tabela_atual: str | None = None
    recomposicoes = 0
    anomalias: list[str] = []

    with pdfplumber.open(fonte) as pdf:
        if len(pdf.pages) != TOTAL_PAGINAS:
            raise AnexoXIExtractionError(
                f"Quantidade de páginas divergente: esperadas {TOTAL_PAGINAS}, obtidas {len(pdf.pages)}"
            )

        for pagina_numero, pagina in enumerate(pdf.pages, start=1):
            tabelas = pagina.extract_tables()
            if not tabelas:
                anomalias.append(f"página {pagina_numero}: nenhuma tabela extraída")
                continue

            for tabela_fisica in tabelas:
                for linha in tabela_fisica:
                    if len(linha) != 5:
                        anomalias.append(
                            f"página {pagina_numero}: linha com {len(linha)} colunas"
                        )
                        continue
                    colunas = [_normalizar(celula) for celula in linha]

                    marcador = colunas[0]
                    if marcador in {"TABELA A", "TABELA B"} and not any(colunas[1:]):
                        tabela_atual = marcador[-1]
                        continue
                    if _e_cabecalho(colunas):
                        continue
                    if tabela_atual is None:
                        anomalias.append(
                            f"página {pagina_numero}: registro antes do marcador normativo"
                        )
                        continue

                    somente_ocupacao = bool(colunas[0]) and not any(colunas[1:])
                    if somente_ocupacao:
                        if (
                            registros_brutos
                            and registros_brutos[-1][0] == tabela_atual
                            and registros_brutos[-1][1][0].endswith("/")
                        ):
                            registros_brutos[-1][1][0] += colunas[0]
                            recomposicoes += 1
                        else:
                            anomalias.append(
                                f"página {pagina_numero}: continuação física inválida"
                            )
                        continue
                    registros_brutos.append((tabela_atual, colunas, pagina_numero))

    registros: list[RegistroAnexoXI] = []
    chaves: set[tuple[str, str, str]] = set()
    duplicados: list[tuple[str, str, str]] = []
    for tabela, colunas, pagina_numero in registros_brutos:
        ocupacao, cnae, descricao, iss, icms = colunas
        erros: list[str] = []
        if not ocupacao:
            erros.append("ocupação vazia")
        if not CNAE_RE.fullmatch(cnae):
            erros.append(f"CNAE inválido: {cnae!r}")
        if not descricao:
            erros.append("descrição vazia")
        if iss not in {"S", "N"}:
            erros.append(f"ISS inválido: {iss!r}")
        if icms not in {"S", "N"}:
            erros.append(f"ICMS inválido: {icms!r}")
        if erros:
            anomalias.append(f"página {pagina_numero}: " + "; ".join(erros))
            continue

        chave = (tabela, ocupacao, cnae)
        if chave in chaves:
            duplicados.append(chave)
            continue
        chaves.add(chave)
        registros.append(
            RegistroAnexoXI(tabela, ocupacao, cnae, descricao, iss == "S", icms == "S", pagina_numero)
        )

    contagens = {
        tabela: sum(registro.tabela == tabela for registro in registros)
        for tabela in CONTAGENS_ESPERADAS
    }
    if contagens != CONTAGENS_ESPERADAS:
        anomalias.append(f"contagens divergentes: esperadas {CONTAGENS_ESPERADAS}, obtidas {contagens}")
    if len(registros) != sum(CONTAGENS_ESPERADAS.values()):
        anomalias.append(f"total divergente: esperado 471, obtido {len(registros)}")
    if recomposicoes != 1:
        anomalias.append(f"recomposições divergentes: esperada 1, obtidas {recomposicoes}")
    if duplicados:
        anomalias.append(f"duplicados exatos: {len(duplicados)}")
    if anomalias:
        raise AnexoXIExtractionError("Extração rejeitada: " + " | ".join(anomalias))

    return ResultadoExtracao(
        registros=tuple(registros),
        paginas=TOTAL_PAGINAS,
        recomposicoes=recomposicoes,
        anomalias=(),
        duplicados=tuple(duplicados),
    )

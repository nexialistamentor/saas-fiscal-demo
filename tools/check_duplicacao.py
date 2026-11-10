#!/usr/bin/env python3
"""
check_duplicacao.py

Catraca executavel anti-duplicacao para o repositorio SOLVERIS Enterprise.

Regra de desenho (doutrina do projeto): memoria/relatorio e a protecao mais
fraca porque nao falha um build. Este script converte a regra "nunca criar
motor_fiscal_v2 / resolver_mva_novo / comparador_B03_alt ao lado do
existente" numa verificacao que FALHA (exit code != 0) quando encontra uma
funcao nova cujo nome e muito parecido com uma funcao ja registada em
REGISTRO_CANONICO.json, sem essa entrada (ou uma nova) declarar
explicitamente 'substitui'.

Uso:
    python check_duplicacao.py --repo C:\\dev\\saas-fiscal-demo-a1 \
        --registro docs/REGISTRO_CANONICO.json

Saida:
    exit 0  -> nada suspeito encontrado
    exit 1  -> duplicacao nao declarada encontrada (lista impressa)
    exit 2  -> erro de uso / ficheiro nao encontrado

Nota deliberada: usa ast.parse / percorre a AST real, nunca grep-com-contexto
(ver /topics/dev-workflow.md -- grep truncou e escondeu coisas em sessoes
anteriores do projeto).
"""

import argparse
import ast
import json
import sys
import difflib
from pathlib import Path

PASTAS_ALVO_DEFAULT = [
    "app/services",
    "tools",
]

PREFIXOS_ENTERPRISE = ("enterprise_",)

LIMIAR_SIMILARIDADE = 0.82  # ajustavel; nomes acima disto sao "suspeitos"


def carregar_registro(caminho_registro: Path) -> dict:
    if not caminho_registro.is_file():
        print(f"ERRO: registo canonico nao encontrado em {caminho_registro}", file=sys.stderr)
        sys.exit(2)
    with caminho_registro.open("r", encoding="utf-8") as f:
        return json.load(f)


def nomes_canonicos_confirmados(registro: dict):
    """
    Retorna lista de (id, nome_funcao_normalizado, caminho_ficheiro, status)
    para cada entrada do registo. Entradas 'a_confirmar' entram tambem --
    ainda nao sao autoridade, mas ja servem de sinal para nao duplicar
    silenciosamente o que ja foi mapeado.
    """
    saida = []
    for mod in registro.get("modulos", []):
        funcao = mod.get("funcao_principal") or ""
        for nome in [n.strip() for n in funcao.replace("|", ",").split(",") if n.strip()]:
            nome_simples = nome.split(".")[-1]  # Classe.metodo -> metodo
            saida.append((mod["id"], nome_simples, mod["modulo_canonico"], mod["status"]))
    return saida


def listar_ficheiros_enterprise(repo_root: Path, pastas: list):
    ficheiros = []
    for pasta in pastas:
        base = repo_root / pasta
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            if any(parte.startswith(PREFIXOS_ENTERPRISE) for parte in p.parts) or p.name.startswith(PREFIXOS_ENTERPRISE):
                ficheiros.append(p)
            else:
                # tambem interessa qualquer .py dentro de app/services e tools,
                # nao so os prefixados enterprise_ -- os 7 modulos do registo
                # incluem nomes sem esse prefixo (motor_fiscal.py, fiscal_utils.py...)
                ficheiros.append(p)
    # remover duplicados preservando ordem
    vistos = set()
    unicos = []
    for f in ficheiros:
        if f not in vistos:
            vistos.add(f)
            unicos.append(f)
    return unicos


FICHEIROS_NAO_ANALISADOS = []  # preenchido em tempo de execucao; reportado no resumo final


def extrair_funcoes_e_metodos(caminho_ficheiro: Path):
    """
    Devolve lista de (nome_funcao, lineno) para todas as funcoes top-level
    e metodos de classe encontrados no ficheiro, via AST real (nao regex).

    Qualquer ficheiro que falhe aqui (leitura ou parse) e registado em
    FICHEIROS_NAO_ANALISADOS e reportado no resumo final MESMO que o
    resultado geral seja OK -- cobertura parcial nunca deve ficar silenciosa.
    """
    try:
        # utf-8-sig tolera BOM (U+FEFF) no inicio do ficheiro, presente ou
        # ausente -- alguns ficheiros do repo tem BOM (ex. escritos via
        # [IO.File]::WriteAllBytes com prefixo 0xEF,0xBB,0xBF), e sem isto
        # o ast.parse falha e o ficheiro fica SILENCIOSAMENTE fora da analise.
        texto = caminho_ficheiro.read_text(encoding="utf-8-sig")
    except (UnicodeDecodeError, OSError) as exc:
        print(f"AVISO: nao consegui ler {caminho_ficheiro}: {exc}", file=sys.stderr)
        FICHEIROS_NAO_ANALISADOS.append((str(caminho_ficheiro), f"leitura: {exc}"))
        return []

    try:
        arvore = ast.parse(texto, filename=str(caminho_ficheiro))
    except SyntaxError as exc:
        print(f"AVISO: SyntaxError em {caminho_ficheiro}: {exc}", file=sys.stderr)
        FICHEIROS_NAO_ANALISADOS.append((str(caminho_ficheiro), f"syntax: {exc}"))
        return []

    encontradas = []
    for node in ast.walk(arvore):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            encontradas.append((node.name, node.lineno))
    return encontradas


def normalizar(nome: str) -> str:
    return nome.lower().replace("_", "")


def verificar(repo_root: Path, registro: dict, pastas: list):
    canonicos = nomes_canonicos_confirmados(registro)
    proibidos = set(registro.get("proibido_por_desenho", []))

    problemas = []

    ficheiros = listar_ficheiros_enterprise(repo_root, pastas)

    for ficheiro in ficheiros:
        caminho_relativo = str(ficheiro.relative_to(repo_root)).replace("\\", "/")
        funcoes = extrair_funcoes_e_metodos(ficheiro)

        for nome_funcao, lineno in funcoes:
            # 1) verificacao direta: nome literalmente proibido por desenho
            if nome_funcao in proibidos or any(normalizar(nome_funcao) == normalizar(p) for p in proibidos):
                problemas.append(
                    f"[PROIBIDO] {caminho_relativo}:{lineno} funcao '{nome_funcao}' "
                    f"corresponde a um nome explicitamente proibido no registo "
                    f"(proibido_por_desenho)."
                )
                continue

            # 2) similaridade com funcoes ja canonicas, em ficheiro DIFERENTE
            for mod_id, nome_canonico, caminho_canonico, status in canonicos:
                if caminho_relativo == caminho_canonico:
                    continue  # e o proprio modulo canonico, nao e duplicacao
                ratio = difflib.SequenceMatcher(
                    None, normalizar(nome_funcao), normalizar(nome_canonico)
                ).ratio()
                if ratio >= LIMIAR_SIMILARIDADE:
                    # permitido se esta entrada (ou outra) declarar 'substitui'
                    # apontando para este ficheiro -- senao, e duplicacao nao declarada
                    declarado = False
                    for mod in registro.get("modulos", []):
                        if caminho_relativo in mod.get("substitui", []):
                            declarado = True
                            break
                    if not declarado:
                        problemas.append(
                            f"[SUSPEITO] {caminho_relativo}:{lineno} funcao '{nome_funcao}' "
                            f"e {ratio:.0%} similar a '{nome_canonico}' (registo id={mod_id}, "
                            f"status={status}) em '{caminho_canonico}', sem declaracao "
                            f"'substitui' no registo. Se for intencional (nova versao "
                            f"substitui a antiga), adicione '{caminho_relativo}' ao campo "
                            f"'substitui' da entrada '{mod_id}' no REGISTRO_CANONICO.json."
                        )

    return problemas


def main():
    parser = argparse.ArgumentParser(description="Catraca anti-duplicacao SOLVERIS Enterprise")
    parser.add_argument("--repo", required=True, help="Raiz do repositorio (ex: C:\\dev\\saas-fiscal-demo-a1)")
    parser.add_argument("--registro", default="docs/REGISTRO_CANONICO.json",
                         help="Caminho do registo canonico, relativo a --repo")
    parser.add_argument("--pastas", nargs="*", default=PASTAS_ALVO_DEFAULT,
                         help="Pastas (relativas a --repo) a vasculhar")
    args = parser.parse_args()

    repo_root = Path(args.repo).resolve()
    if not repo_root.is_dir():
        print(f"ERRO: repo nao encontrado em {repo_root}", file=sys.stderr)
        sys.exit(2)

    caminho_registro = repo_root / args.registro
    registro = carregar_registro(caminho_registro)

    problemas = verificar(repo_root, registro, args.pastas)

    if FICHEIROS_NAO_ANALISADOS:
        print(f"\n{'=' * 70}")
        print(f"COBERTURA PARCIAL: {len(FICHEIROS_NAO_ANALISADOS)} ficheiro(s) NAO analisado(s)")
        print(f"{'=' * 70}")
        for caminho, motivo in FICHEIROS_NAO_ANALISADOS:
            print(f" - {caminho} ({motivo})")
        print(
            "\nEstes ficheiros NAO foram verificados contra duplicacao. "
            "Um resultado 'OK' abaixo NAO cobre estes ficheiros.\n"
        )

    if problemas:
        print(f"\n{'=' * 70}")
        print(f"DUPLICACAO_NAO_DECLARADA: {len(problemas)} ocorrencia(s)")
        print(f"{'=' * 70}\n")
        for p in problemas:
            print(f" - {p}")
        print()
        sys.exit(1)

    if FICHEIROS_NAO_ANALISADOS:
        print("PARCIAL: nenhuma duplicacao encontrada nos ficheiros analisados, "
              "mas ha ficheiros fora da cobertura (ver lista acima).")
        sys.exit(3)

    print("OK: nenhuma duplicacao nao declarada encontrada (cobertura completa).")
    sys.exit(0)


if __name__ == "__main__":
    main()

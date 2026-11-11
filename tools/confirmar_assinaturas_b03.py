#!/usr/bin/env python3
"""
confirmar_assinaturas_b03.py

Fase 0 do B03: mostra as assinaturas REAIS (via AST, nao grep-com-contexto)
dos 7 modulos que o relatorio GPT alega ja existirem, lendo diretamente do
registo canonico. Para cada modulo imprime: classes, funcoes top-level,
metodos, argumentos, e a primeira linha do docstring (se existir) -- o
suficiente para confirmar ou refutar a alegacao do relatorio sem copiar
ficheiros inteiros para o chat.

Uso:
    python confirmar_assinaturas_b03.py --repo C:\\dev\\saas-fiscal-demo-a1 \
        --registro docs/REGISTRO_CANONICO.json

Depois de cada modulo confirmado, atualizar manualmente o campo 'status'
de 'a_confirmar' para 'confirmado' (ou corrigir 'funcao_principal' se a
assinatura real divergir) no REGISTRO_CANONICO.json.
"""

import argparse
import ast
import json
import sys
from pathlib import Path


def ler_arvore(caminho: Path):
    try:
        texto = caminho.read_text(encoding="utf-8-sig")
    except (UnicodeDecodeError, OSError) as exc:
        return None, f"ERRO_LEITURA: {exc}"
    try:
        return ast.parse(texto, filename=str(caminho)), None
    except SyntaxError as exc:
        return None, f"ERRO_SYNTAX: {exc}"


def args_de(node) -> str:
    partes = []
    for a in node.args.args:
        partes.append(a.arg)
    if node.args.vararg:
        partes.append("*" + node.args.vararg.arg)
    for a in node.args.kwonlyargs:
        partes.append(a.arg + "=...")
    if node.args.kwarg:
        partes.append("**" + node.args.kwarg.arg)
    return ", ".join(partes)


def primeira_linha_docstring(node) -> str:
    doc = ast.get_docstring(node)
    if not doc:
        return ""
    return doc.strip().splitlines()[0][:100]


def descrever_modulo(arvore: ast.Module):
    linhas = []
    for node in arvore.body:
        if isinstance(node, ast.ClassDef):
            linhas.append(f"  class {node.name}:")
            doc = primeira_linha_docstring(node)
            if doc:
                linhas.append(f"      # {doc}")
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    linhas.append(f"      def {sub.name}({args_de(sub)})  [linha {sub.lineno}]")
                    doc2 = primeira_linha_docstring(sub)
                    if doc2:
                        linhas.append(f"          # {doc2}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            linhas.append(f"  def {node.name}({args_de(node)})  [linha {node.lineno}]")
            doc = primeira_linha_docstring(node)
            if doc:
                linhas.append(f"      # {doc}")
    return linhas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--registro", default="docs/REGISTRO_CANONICO.json")
    args = parser.parse_args()

    repo_root = Path(args.repo).resolve()
    caminho_registro = repo_root / args.registro
    if not caminho_registro.is_file():
        print(f"ERRO: registo nao encontrado em {caminho_registro}", file=sys.stderr)
        sys.exit(2)

    registro = json.loads(caminho_registro.read_text(encoding="utf-8-sig"))

    for mod in registro.get("modulos", []):
        caminho = repo_root / mod["modulo_canonico"]
        print(f"\n{'=' * 78}")
        print(f"id={mod['id']}  status_registo={mod['status']}")
        print(f"ficheiro: {mod['modulo_canonico']}")
        print(f"alegado (relatorio): {mod.get('funcao_principal') or '(nao especificado)'}")
        print(f"{'=' * 78}")

        if not caminho.is_file():
            print("  >>> FICHEIRO NAO EXISTE NESTE CAMINHO -- alegacao do relatorio REFUTADA")
            continue

        arvore, erro = ler_arvore(caminho)
        if erro:
            print(f"  >>> {erro} -- nao foi possivel confirmar por este metodo")
            continue

        linhas = descrever_modulo(arvore)
        if not linhas:
            print("  >>> ficheiro existe mas nao tem classes/funcoes top-level visiveis")
        else:
            for l in linhas:
                print(l)


if __name__ == "__main__":
    main()

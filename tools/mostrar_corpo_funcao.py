#!/usr/bin/env python3
"""
mostrar_corpo_funcao.py

Mostra o corpo EXATO de uma funcao/metodo de um ficheiro Python, via
ast.get_source_segment (nunca grep-com-contexto -- licao MISSION-014,
que ja escondeu divergencias nesta sessao por truncar).

Uso:
    python mostrar_corpo_funcao.py --ficheiro app/services/fiscal_utils.py --funcao resolver_aliquota_e_mva
    python mostrar_corpo_funcao.py --ficheiro app/motor_fiscal.py --funcao analisar_xml
"""
import argparse
import ast
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ficheiro", required=True)
    parser.add_argument("--funcao", required=True, help="nome da funcao ou metodo (sem Classe.)")
    args = parser.parse_args()

    caminho = Path(args.ficheiro)
    if not caminho.is_file():
        print(f"ERRO: ficheiro nao encontrado: {caminho}", file=sys.stderr)
        sys.exit(2)

    texto = caminho.read_text(encoding="utf-8-sig")
    arvore = ast.parse(texto, filename=str(caminho))

    encontrados = []
    for node in ast.walk(arvore):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == args.funcao:
            encontrados.append(node)

    if not encontrados:
        print(f"NAO ENCONTRADA: nenhuma funcao/metodo chamado '{args.funcao}' em {caminho}")
        sys.exit(1)

    for node in encontrados:
        segmento = ast.get_source_segment(texto, node)
        print(f"\n{'=' * 78}")
        print(f"{caminho}  linha {node.lineno}-{node.end_lineno}")
        print(f"{'=' * 78}")
        print(segmento)


if __name__ == "__main__":
    main()

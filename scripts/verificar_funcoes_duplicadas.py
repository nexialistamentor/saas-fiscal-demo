import ast
import os
from collections import defaultdict

BASE_DIR = "app"

funcoes = defaultdict(list)

for root, dirs, files in os.walk(BASE_DIR):
    for file in files:
        if file.endswith(".py"):
            caminho = os.path.join(root, file)
            with open(caminho, "r", encoding="utf-8") as f:
                try:
                    tree = ast.parse(f.read())
                except Exception:
                    continue

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    funcoes[node.name].append(caminho)

print("\nFunções duplicadas encontradas:\n")

duplicadas = False

for nome, locais in sorted(funcoes.items()):
    if len(locais) > 1:
        duplicadas = True
        print(f"Função: {nome}")
        for l in locais:
            print("  -", l)
        print()

if not duplicadas:
    print("Nenhuma função duplicada encontrada.")

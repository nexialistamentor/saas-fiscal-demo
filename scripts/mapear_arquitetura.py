import os
import ast

BASE_DIR = "app"

arquivos = []
funcoes = []
classes = []

for root, dirs, files in os.walk(BASE_DIR):
    for file in files:
        if file.endswith(".py"):
            caminho = os.path.join(root, file)
            arquivos.append(caminho)

            try:
                with open(caminho, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        funcoes.append((node.name, caminho))

                    if isinstance(node, ast.ClassDef):
                        classes.append((node.name, caminho))

            except Exception:
                pass

print("\n=== ARQUIVOS PYTHON ===\n")
for a in sorted(arquivos):
    print(a)

print("\n=== CLASSES ===\n")
for c in classes:
    print(f"{c[0]}  ->  {c[1]}")

print("\n=== FUNÇÕES ===\n")
for f in funcoes:
    print(f"{f[0]}  ->  {f[1]}")

print("\nResumo:")
print("Arquivos:", len(arquivos))
print("Classes:", len(classes))
print("Funções:", len(funcoes))

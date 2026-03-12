import ast
import os
from collections import defaultdict

BASE_DIR = "app"

imports = defaultdict(set)

for root, _, files in os.walk(BASE_DIR):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for n in node.names:
                        imports[path].add(n.name)
                if isinstance(node, ast.ImportFrom):
                    module = node.module if node.module else ""
                    imports[path].add(module)

print("\n=== DEPENDÊNCIAS ENTRE MÓDULOS ===\n")
for k, v in sorted(imports.items()):
    print(k)
    for m in sorted(v):
        print("  ->", m)
    print()

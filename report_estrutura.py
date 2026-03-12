import os

pastas = [
    "app/routes",
    "app/services",
    "app/services/tax_engines",
    "app/services/tax_consistency",
    "app/agents",
]

print("\nRELATÓRIO ESTRUTURAL DA PLATAFORMA\n")

for pasta in pastas:
    print(f"\n[{pasta}]")
    if os.path.exists(pasta):
        for root, dirs, files in os.walk(pasta):
            nivel = root.replace(pasta, "").count(os.sep)
            indent = "  " * nivel
            print(f"{indent}{os.path.basename(root)}/")
            subindent = "  " * (nivel + 1)
            for f in files:
                print(f"{subindent}{f}")
    else:
        print("  Pasta não encontrada")

print("\nFIM DO RELATÓRIO\n")

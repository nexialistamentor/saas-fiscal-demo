# -*- coding: utf-8 -*-
"""Script de auditoria de integração (Pipeline + Oportunidades + Score)"""
import os
import re

checks = {
    "PIPELINE_UPLOAD_XML": [
        "app/routes/fiscal_router.py",
        "app/xml_service.py",
        "app/motor_fiscal.py"
    ],
    "CONSISTENCY_ENGINE": [
        "app/services/tax_consistency/tax_consistency_engine.py"
    ],
    "INSIGHTS_ENGINE": [
        "app/services/insights_engine.py"
    ],
    "ALERTAS_FISCAIS": [
        "app/models.py",
        "app/services"
    ],
    "SCORING_TRIBUTARIO": [
        "score", "risk", "potencial", "ranking"
    ]
}

print("\nAUDITORIA DE INTEGRAÇÃO DA PLATAFORMA\n")

# 1) Checar arquivos-chave
for bloco, paths in checks.items():
    ok = False
    for p in paths:
        if os.path.exists(p):
            ok = True
    status = "OK" if ok else "NÃO ENCONTRADO"
    print(f"{bloco}: {status}")

# 2) Procurar indícios de scoring
score_hits = []
for root, _, files in os.walk("app"):
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    txt = fh.read().lower()
                    if re.search(r"(score|risk|ranking|potencial)", txt):
                        score_hits.append(path)
            except Exception:
                pass

print("\nArquivos com possíveis métricas/score:")
for p in score_hits[:15]:
    print("-", p)

print("\nFIM DA AUDITORIA\n")

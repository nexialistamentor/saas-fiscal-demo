"""
seed_referencias_legais.py — Soberana L2

Seed inicial da tabela referencias_legais.
Mapeia cada tipo de Insight para o fundamento legal correspondente.

Usar: python -m app.scripts.seed_referencias_legais
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from datetime import date

from app.database import SessionLocal
from app.models import ReferenciaLegal

REFERENCIAS = [
    {
        "codigo": "ST_RESTITUICAO",
        "titulo": "Restituição de ICMS-ST",
        "fundamento": "Art. 150, §7º CF/88 + Convênio ICMS 142/2018 + RE 593849 STF",
        "descricao": "Direito à restituição do ICMS-ST recolhido antecipadamente quando a base de cálculo real for inferior à presumida.",
        "vigencia_inicio": date(2018, 12, 20),
    },
    {
        "codigo": "ESTOQUE_FANTASMA_NCM",
        "titulo": "Estoque Fantasma — ST sem Saída por NCM",
        "fundamento": "Art. 150, §7º CF/88 + Convênio ICMS 142/2018",
        "descricao": "ST paga na entrada sem saída correspondente indica mercadoria ainda em estoque ou perda não registada — base para pedido de restituição.",
        "vigencia_inicio": date(2018, 12, 20),
    },
    {
        "codigo": "ST_SEM_SAIDA",
        "titulo": "ICMS-ST sem Saída Correspondente",
        "fundamento": "Art. 150, §7º CF/88 + RE 593849 STF (Tema 201)",
        "descricao": "Saldo de ST nas entradas superior às saídas — evidência de crédito a recuperar.",
        "vigencia_inicio": date(2011, 10, 19),
    },
    {
        "codigo": "ANOMALIA_MVA",
        "titulo": "Anomalia na Margem de Valor Agregado",
        "fundamento": "Convênio ICMS 142/2018 + legislação estadual de MVA por NCM",
        "descricao": "Preço de venda inferior à base de ST presumida — indica possível recolhimento de ST acima do devido.",
        "vigencia_inicio": date(2018, 12, 20),
    },
    {
        "codigo": "MVA_OFICIAL_DIVERGENTE",
        "titulo": "Divergência entre MVA Aplicada e MVA Oficial",
        "fundamento": "Convênio ICMS 142/2018 + Protocolo ICMS do estado",
        "descricao": "MVA utilizada na NF-e diverge da MVA oficial tabelada — pode indicar erro de parametrização ou oportunidade de revisão.",
        "vigencia_inicio": date(2018, 12, 20),
    },
    {
        "codigo": "CONCENTRACAO_ST_NCM",
        "titulo": "Concentração de ST em NCM Específico",
        "fundamento": "Convênio ICMS 142/2018 + RE 593849 STF",
        "descricao": "NCM responsável por mais de 40% da ST total — risco concentrado e oportunidade prioritária de revisão.",
        "vigencia_inicio": date(2018, 12, 20),
    },
    {
        "codigo": "DISTORCAO_MARGEM_MVA",
        "titulo": "Distorção entre Margem Real e MVA Presumida",
        "fundamento": "Convênio ICMS 142/2018 + RE 593849 STF (Tema 201)",
        "descricao": "Margem real apurada nas operações diverge significativamente da MVA presumida — base para pedido de restituição.",
        "vigencia_inicio": date(2011, 10, 19),
    },
    {
        "codigo": "CREDITO_ST_ESTIMADO",
        "titulo": "Crédito de ICMS-ST Estimado",
        "fundamento": "Art. 150, §7º CF/88 + Convênio ICMS 142/2018",
        "descricao": "ST recolhida acima do valor devido — crédito estimado disponível para compensação ou restituição.",
        "vigencia_inicio": date(2018, 12, 20),
    },
    {
        "codigo": "DISTORCAO_MVA_REAL",
        "titulo": "Distorção de MVA Real vs Tabelada",
        "fundamento": "Convênio ICMS 142/2018",
        "descricao": "MVA real das operações diverge da MVA tabelada em mais de 20% — indica parametrização incorreta.",
        "vigencia_inicio": date(2018, 12, 20),
    },
    {
        "codigo": "RESTITUICAO_POSSIVEL",
        "titulo": "Restituição de ST Possível",
        "fundamento": "Art. 150, §7º CF/88 + RE 593849 STF + Convênio ICMS 142/2018",
        "descricao": "ST recolhida acima do valor correto — pedido de restituição administrativo recomendado.",
        "vigencia_inicio": date(2011, 10, 19),
    },
    {
        "codigo": "RISCO_FISCAL",
        "titulo": "Risco Fiscal — ST Recolhida Abaixo do Devido",
        "fundamento": "Art. 155, §2º, XII, b CF/88 + RICMS estadual",
        "descricao": "ST recolhida abaixo do valor correto — risco de autuação fiscal. Verificar parametrização.",
        "vigencia_inicio": date(1988, 10, 5),
    },
    {
        "codigo": "ALERTA_PREDITIVO_TRIBUTARIO",
        "titulo": "Alerta Preditivo Tributário",
        "fundamento": "Convênio ICMS 142/2018 + análise estatística de operações",
        "descricao": "Tendência de impacto tributário detectada com base no padrão atual de operações.",
        "vigencia_inicio": date(2018, 12, 20),
    },
    {
        "codigo": "PRODUTO_COM_RESTITUICAO_RELEVANTE",
        "titulo": "Produto com Restituição Relevante",
        "fundamento": "Art. 150, §7º CF/88 + RE 593849 STF + Convênio ICMS 142/2018",
        "descricao": "NCM com maior potencial de restituição estimada — prioridade no pedido administrativo.",
        "vigencia_inicio": date(2011, 10, 19),
    },
    {
        "codigo": "QUALIDADE_DADOS_UF_BAIXA",
        "titulo": "Qualidade de Dados — Cobertura de UF Baixa",
        "fundamento": "Protocolo interno de qualidade de dados Soberana L2",
        "descricao": "Menos de 50% dos documentos fiscais têm UF identificada — reduz precisão dos cálculos estaduais.",
        "vigencia_inicio": date(2026, 1, 1),
    },
    {
        "codigo": "ICMS_RECUPERAVEL",
        "titulo": "ICMS Recuperável",
        "fundamento": "Art. 150, §7º CF/88 + RE 593849 STF",
        "descricao": "Crédito de ICMS identificado passível de compensação ou restituição.",
        "vigencia_inicio": date(2011, 10, 19),
    },
]


def seed():
    db = SessionLocal()
    try:
        inseridos = 0
        actualizados = 0
        for ref in REFERENCIAS:
            existente = db.query(ReferenciaLegal).filter(
                ReferenciaLegal.codigo == ref["codigo"]
            ).first()
            if existente:
                existente.titulo = ref["titulo"]
                existente.fundamento = ref["fundamento"]
                existente.descricao = ref.get("descricao")
                existente.vigencia_inicio = ref["vigencia_inicio"]
                actualizados += 1
            else:
                novo = ReferenciaLegal(
                    codigo=ref["codigo"],
                    titulo=ref["titulo"],
                    fundamento=ref["fundamento"],
                    descricao=ref.get("descricao"),
                    uf=ref.get("uf"),
                    vigencia_inicio=ref["vigencia_inicio"],
                    vigencia_fim=ref.get("vigencia_fim"),
                    fonte_url=ref.get("fonte_url"),
                )
                db.add(novo)
                inseridos += 1
        db.commit()
        print(
            f"Seed concluído: {inseridos} inseridos, {actualizados} actualizados."
        )
    except Exception as e:
        db.rollback()
        print(f"Erro no seed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()

from app.services.tax_engines.lucro_presumido_engine import calcular_lucro_presumido
from app.services.tax_engines.lucro_real_engine import calcular_lucro_real
from app.services.tax_engines.response_formatter import formatar_resposta_tributaria


def calcular_impostos_empresa(empresa, dados_fiscais: dict):

    regime = empresa.regime_tributario

    if regime == "presumido":
        return calcular_lucro_presumido(dados_fiscais)

    elif regime == "real":
        return calcular_lucro_real(dados_fiscais)

    elif regime == "simples":
        return formatar_resposta_tributaria(
            regime="simples_nacional",
            tributos={"irpj": 0, "csll": 0, "pis": 0, "cofins": 0},
            bases_calculo={"base_irpj": 0, "base_csll": 0, "faturamento": 0},
            alertas=["Cálculo direcionado para motor do Simples Nacional."]
        )

    elif regime == "mei":
        return formatar_resposta_tributaria(
            regime="mei",
            tributos={"irpj": 0, "csll": 0, "pis": 0, "cofins": 0},
            bases_calculo={"base_irpj": 0, "base_csll": 0, "faturamento": 0},
            alertas=["Use o serviço de cálculo MEI existente."]
        )

    else:
        return formatar_resposta_tributaria(
            regime="nao_identificado",
            tributos={"irpj": 0, "csll": 0, "pis": 0, "cofins": 0},
            bases_calculo={"base_irpj": 0, "base_csll": 0, "faturamento": 0},
            alertas=["Empresa sem regime tributário definido."]
        )

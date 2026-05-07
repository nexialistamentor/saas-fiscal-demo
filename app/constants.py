"""Constantes globais da plataforma — fonte única de verdade."""

VERSAO_TERMOS_ATUAL = "1.0"
TERMOS_CACHE_TTL = 300  # segundos (5 minutos)

# LGPD
VERSAO_POLITICA_PRIVACIDADE = "1.0"
FINALIDADE_SIMULACAO = "simulacao_tributaria"
LGPD_CACHE_TTL = 300  # segundos

# Agentes de Abertura e Encerramento

ANALYSIS_TYPE_ABERTURA = "abertura_empresa"

ANALYSIS_TYPE_ENCERRAMENTO = "encerramento_empresa"

# Sinónimos para detecção de intenção — abertura

PALAVRAS_ABERTURA = [
    "abrir empresa", "abrir mei", "abrir negócio", "formalizar", "formalização",
    "registrar empresa", "cnpj", "redesim", "portal do empreendedor",
    "virar mei", "ser mei", "como abro", "quero abrir", "abrir cnpj",
    "microempreendedor", "microempresa", "me abrir", "constituir empresa",
]

# Sinónimos para detecção de intenção — encerramento

PALAVRAS_ENCERRAMENTO = [
    "fechar empresa", "fechar mei", "encerrar", "encerramento", "baixa",
    "baixar cnpj", "cancelar mei", "extinguir", "encerrar cnpj",
    "dar baixa", "fechar negócio", "como fecho", "quero fechar",
    "encerrar empresa", "liquidar empresa",
]

# Checklist MEI — Abertura

CHECKLIST_ABERTURA_MEI = [
    {"passo": 1, "titulo": "Verificar CPF", "descricao": "CPF regular, sem pendências eleitorais ou suspensão.", "link": "https://www.gov.br/receitafederal"},
    {"passo": 2, "titulo": "Conta gov.br nível Prata ou Ouro", "descricao": "Contas Bronze não permitem formalização MEI.", "link": "https://www.gov.br/governodigital"},
    {"passo": 3, "titulo": "Verificar se já tem MEI ativo", "descricao": "Cada CPF só pode ter um MEI ativo.", "link": "https://www.gov.br/empresas-e-negocios"},
    {"passo": 4, "titulo": "Definir CNAE (atividade)", "descricao": "Consultar lista de ocupações permitidas para MEI.", "link": "https://www.gov.br/empresas-e-negocios/pt-br/empreendedor"},
    {"passo": 5, "titulo": "Acessar Portal do Empreendedor", "descricao": "Preencher dados e emitir CNPJ — gratuito, na hora.", "link": "https://www.gov.br/empresas-e-negocios/pt-br/empreendedor"},
    {"passo": 6, "titulo": "Emitir primeiro DAS", "descricao": "Boleto do mês seguinte à abertura.", "link": "https://www8.receita.fazenda.gov.br/SimplesNacional/Aplicacoes/ATBHE/pgmei.app/Identificacao"},
    {"passo": 7, "titulo": "Abrir conta PJ", "descricao": "Separar finanças pessoais das empresariais."},
    {"passo": 8, "titulo": "Declaração Anual (DASN-SIMEI)", "descricao": "Entregar até 31 de maio de cada ano.", "link": "https://www.gov.br/empresas-e-negocios/pt-br/empreendedor"},
]

# Checklist ME/EPP — Abertura

CHECKLIST_ABERTURA_ME_EPP = [
    {"passo": 1, "titulo": "Contratar contador", "descricao": "Obrigatório para ME e EPP."},
    {"passo": 2, "titulo": "Definir natureza jurídica", "descricao": "EI, SLU ou Ltda — com o contador."},
    {"passo": 3, "titulo": "Verificar viabilidade de nome e endereço", "descricao": "Consultar na Junta Comercial e prefeitura."},
    {"passo": 4, "titulo": "Registro na Junta Comercial via REDESIM", "descricao": "Obter CNPJ, Inscrição Estadual e Municipal.", "link": "https://redesim.gov.br"},
    {"passo": 5, "titulo": "Licenças", "descricao": "Funcionamento, ambiental e sanitária conforme atividade."},
    {"passo": 6, "titulo": "Certificado Digital e-CNPJ", "descricao": "Necessário para emissão de NF-e."},
    {"passo": 7, "titulo": "Inscrição no Simples Nacional", "descricao": "Se aplicável — prazo de 30 dias após abertura.", "link": "https://www8.receita.fazenda.gov.br/SimplesNacional"},
]

# Checklist — Encerramento

CHECKLIST_ENCERRAMENTO = [
    {"passo": 1, "titulo": "Verificar DAS em atraso", "descricao": "Quitar todos os DAS pendentes antes da baixa.", "severidade": "alta"},
    {"passo": 2, "titulo": "Entregar DASN de extinção", "descricao": "Declarar faturamento proporcional até à data de encerramento.", "severidade": "alta"},
    {"passo": 3, "titulo": "Verificar débitos federais", "descricao": "Consultar pendências na Receita Federal.", "severidade": "alta", "link": "https://www.gov.br/receitafederal"},
    {"passo": 4, "titulo": "Verificar débitos estaduais (ICMS)", "descricao": "Consultar SEFAZ do estado.", "severidade": "alta"},
    {"passo": 5, "titulo": "Verificar débitos municipais (ISS)", "descricao": "Consultar portal da prefeitura.", "severidade": "media"},
    {"passo": 6, "titulo": "Solicitar baixa", "descricao": "MEI: Portal do Empreendedor. ME/EPP: Junta Comercial via REDESIM.", "severidade": "alta"},
    {"passo": 7, "titulo": "Obter Certidões Negativas", "descricao": "CND Federal, Estadual e Municipal.", "severidade": "alta"},
    {"passo": 8, "titulo": "Guardar documentos por 5 anos", "descricao": "Obrigação legal — CTN art. 195.", "severidade": "media"},
]

AVISO_ENCERRAMENTO_IRREVERSIVEL = (
    "⚠️ ATENÇÃO: O encerramento é irreversível. Débitos não quitados migram para o CPF do titular. "
    "O MEI continua obrigado a pagar o DAS até que a baixa seja concluída."
)

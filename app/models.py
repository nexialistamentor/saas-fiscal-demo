from datetime import datetime
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.types import JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


# =========================
# PLANO
# =========================
class Plano(Base):
    __tablename__ = "planos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    limite_cnpjs = Column(Integer, nullable=False)
    limite_analises = Column(Integer, default=100, nullable=False)  # análises/mês por empresa

    usuarios = relationship("User", back_populates="plano")


# =========================
# USER
# =========================
ROLES_VALIDOS = ("user", "admin", "contador")


class User(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint(
            f"role IN ({', '.join(repr(r) for r in ROLES_VALIDOS)})",
            name="ck_usuarios_role_valido",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    plano_id = Column(Integer, ForeignKey("planos.id"), nullable=True)
    consulta_paga = Column(Boolean, default=False, nullable=False)
    role = Column(String(20), nullable=False, default="user", server_default="user", index=True)
    cpf = Column(String(11), nullable=True, unique=True, index=True)

    plano = relationship("Plano", back_populates="usuarios")
    empresas = relationship("Empresa", back_populates="owner")
    documentos_rendimento = relationship("DocumentoRendimento", back_populates="owner")

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


# Regimes tributários esperados pelo regime_router (fluxo BLOCO 10)
# empresa → regime_tributario → regime_router → engine tributário correto
REGIMES_TRIBUTARIOS = ("simples", "presumido", "real", "mei")


# =========================
# EMPRESA
# =========================
class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, index=True)
    cnpj = Column(String, nullable=True)
    razao_social = Column(String, nullable=True)
    regime_tributario = Column(String, nullable=True, index=True)  # simples | presumido | real | mei

    user_id = Column(Integer, ForeignKey("usuarios.id"))

    owner = relationship("User", back_populates="empresas")
    documentos_fiscais = relationship("DocumentoFiscal", back_populates="empresa")


# =========================
# DOCUMENTO FISCAL
# =========================
class DocumentoFiscal(Base):
    __tablename__ = "documentos_fiscais"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id",
            "conteudo_sha256",
            name="uq_documentos_fiscais_empresa_conteudo_sha256",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    # SHA-256 hex (64 chars) dos bytes brutos do XML; deduplica reenvio idêntico por empresa.
    conteudo_sha256 = Column(String(64), nullable=True)
    chave_nfe = Column(String, nullable=True)
    numero_nota = Column(String, nullable=True)
    data_emissao = Column(Date, nullable=True)
    tipo = Column(String, nullable=True)
    valor_total = Column(Float, nullable=True)
    mva_utilizada = Column(Float, nullable=True)
    uf_emit = Column(String(2), nullable=True)
    uf_dest = Column(String(2), nullable=True)

    empresa = relationship("Empresa", back_populates="documentos_fiscais")
    itens = relationship("ItemFiscal", back_populates="documento", cascade="all, delete-orphan")


# =========================
# ITEM FISCAL
# =========================
class ItemFiscal(Base):
    __tablename__ = "itens_fiscais"

    id = Column(Integer, primary_key=True, index=True)
    documento_id = Column(Integer, ForeignKey("documentos_fiscais.id"))
    quantidade = Column(Float, nullable=True)
    ncm = Column(String, nullable=True)
    cfop = Column(String, nullable=True)
    valor_produto = Column(Float, nullable=True)
    base_icms = Column(Float, nullable=True)
    valor_icms = Column(Float, nullable=True)
    base_st = Column(Float, nullable=True)
    valor_st = Column(Float, nullable=True)

    documento = relationship("DocumentoFiscal", back_populates="itens")


# Alias para consultas de NF-e
NotaFiscalItem = ItemFiscal


# =========================
# TABELA MVA
# =========================
class TabelaMVA(Base):
    __tablename__ = "tabela_mva"

    id = Column(Integer, primary_key=True, index=True)

    estado = Column(String, index=True)
    ncm = Column(String, index=True)

    mva = Column(Float)
    aliquota_interna = Column(Float)

    vigencia_inicio = Column(Date)
    vigencia_fim = Column(Date, nullable=True)

    fonte_legal = Column(String(500), nullable=True)  # ex: "Portaria SEFAZ/PA 058/2023"
    url_fonte = Column(String(1000), nullable=True)  # link oficial quando disponível
    importado_em = Column(DateTime, default=func.now(), nullable=True)
    importado_por = Column(String(100), nullable=True)  # ex: "importar_mva_pa.py v1.0"


# =========================
# SNAPSHOT INTELIGÊNCIA (Memória Estratégica Tributária)
# =========================
class InteligenciaSnapshot(Base):
    __tablename__ = "inteligencia_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    score_global = Column(Float)
    risco_tributario = Column(String)
    maturidade_tributaria = Column(String)
    uf_cobertura = Column(Float, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)


# =========================
# ALERTA FISCAL
# =========================
class AlertaFiscal(Base):
    __tablename__ = "alertas_fiscais"

    id = Column(Integer, primary_key=True, index=True)
    agente = Column(String, index=True)
    tipo = Column(String)
    descricao = Column(String)
    nivel = Column(String)
    empresa_id = Column(Integer)
    relatorio_analise_id = Column(Integer, ForeignKey("relatorios_analise.id"), nullable=True, index=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    silenciado = Column(Boolean, default=False)


# =========================
# RELATÓRIO MEI (persistido para GET por ID)
# =========================
class RelatorioMei(Base):
    __tablename__ = "relatorios_mei"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    resultado = Column(Text, nullable=False)  # JSON do resultado de calcular_imposto_simples
    criado_em = Column(DateTime, default=datetime.utcnow)


# =========================
# RELATÓRIO ANÁLISE (container completo da execução de análise)
# mei_tax | tax_planning | tax_recovery | empresa_tax | xml_analise
# Cada execução vira um registro completo auditável.
# =========================
class RelatorioAnalise(Base):
    __tablename__ = "relatorios_analise"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=True, index=True)

    analysis_type = Column(String, index=True)
    # mei_tax | tax_planning | tax_recovery | empresa_tax | xml_analise

    xml_chave = Column(String, nullable=True, index=True)  # chave NF-e quando análise via XML
    status = Column(String, nullable=True, index=True)  # ok | erro | processando
    tempo_execucao = Column(Float, nullable=True)  # segundos
    total_alertas = Column(Integer, default=0, nullable=True)
    score_resultante = Column(Float, nullable=True)  # score tributário ao final da análise

    resultado_json = Column(JSON)
    fingerprint = Column(String(64), nullable=True)

    pago = Column(Boolean, default=False, nullable=False)
    memorial_gerado = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================
# INSIGHT
# =========================
class Insight(Base):
    __tablename__ = "insights"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    relatorio_analise_id = Column(Integer, ForeignKey("relatorios_analise.id"), nullable=True, index=True)
    tipo = Column(String, nullable=False, index=True)
    valor_estimado = Column(Float, nullable=True, default=0)
    impacto = Column(String, nullable=True)
    descricao = Column(String, nullable=True)
    recomendacao = Column(String, nullable=True)
    ncm = Column(String, nullable=True, index=True)
    payload_json = Column(JSON, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    superseded = Column(Boolean, default=False, nullable=False, server_default="false")


# =========================
# SNAPSHOT MÉTRICAS (histórico de desempenho das engines)
# =========================
class MetricasSnapshot(Base):
    __tablename__ = "metricas_snapshot"

    id = Column(Integer, primary_key=True, index=True)
    total_execucoes = Column(Integer)
    total_erros = Column(Integer)
    tempo_total = Column(Float)
    tempo_medio = Column(Float)
    por_tipo = Column(JSON)

    criado_em = Column(DateTime(timezone=True), server_default=func.now())


# =========================
# USO PLATAFORMA (billing / rate control por empresa)
# =========================
class UsoPlataforma(Base):
    __tablename__ = "uso_plataforma"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, index=True)

    analises_mes = Column(Integer, default=0)
    xmls_processados = Column(Integer, default=0)

    mes = Column(Integer)
    ano = Column(Integer)


# =========================
# RESULTADO DAS ENGINES (histórico para análise e dashboards)
# =========================
# =========================
# AUDITORIA ESTOQUE (comparação fiscal x ERP)
# =========================
class AuditoriaEstoque(Base):
    __tablename__ = "auditoria_estoque"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, nullable=True)
    ncm = Column(String(20), nullable=True)
    estoque_fiscal = Column(Float, nullable=True)
    estoque_erp = Column(Float, nullable=True)
    diferenca = Column(Float, nullable=True)
    risco_desvio = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# =========================
# DOCUMENTO RENDIMENTO (CPF)
# =========================
TIPOS_RENDIMENTO = ("salario", "autonomo", "aluguel", "investimento", "outro")


class DocumentoRendimento(Base):
    __tablename__ = "documentos_rendimento"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    tipo_rendimento = Column(String(20), nullable=False)
    descricao = Column(String, nullable=True)
    valor = Column(Float, nullable=True)
    ano_referencia = Column(Integer, nullable=True)
    mes_referencia = Column(Integer, nullable=True)
    arquivo_nome = Column(String, nullable=True)
    arquivo_path = Column(String, nullable=True)
    fonte_pagadora = Column(String, nullable=True)
    confianca_extracao = Column(String(10), nullable=True)  # alta | media | baixa | manual
    campos_corrigidos = Column(JSON, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="documentos_rendimento")


# =========================
# REFERÊNCIAS LEGAIS (base normativa do Memorial de Cálculo)
# =========================
class ReferenciaLegal(Base):
    __tablename__ = "referencias_legais"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(50), unique=True, nullable=False, index=True)
    titulo = Column(String(200), nullable=False)
    fundamento = Column(Text, nullable=False)
    descricao = Column(Text, nullable=True)
    uf = Column(String(2), nullable=True, index=True)
    vigencia_inicio = Column(Date, nullable=False)
    vigencia_fim = Column(Date, nullable=True)
    fonte_url = Column(String(500), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =========================
# RESULTADO DAS ENGINES
# =========================
class EngineResultado(Base):
    __tablename__ = "engine_resultados"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, index=True)
    relatorio_analise_id = Column(Integer, ForeignKey("relatorios_analise.id"), nullable=True, index=True)
    engine_nome = Column(String, index=True)
    resultado = Column(JSON)
    criado_em = Column(DateTime, default=datetime.utcnow)


# =========================
# REQUEST LOG (tráfego HTTP)
# =========================
class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(Integer, primary_key=True, index=True)
    criado_em = Column(DateTime, default=func.now(), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    path = Column(String(500), nullable=False)
    status_code = Column(Integer, nullable=True)
    user_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    ip = Column(String(45), nullable=False)
    user_agent = Column(String(500), nullable=True)
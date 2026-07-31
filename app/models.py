from datetime import datetime
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
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

    # Campos financeiros soberanos
    preco = Column(Numeric(10, 2), nullable=False, default=0)
    billing_type = Column(String, nullable=False, default="monthly")  # monthly, yearly, one_time
    ativo = Column(Boolean, default=True, nullable=False)
    tipo_acesso = Column(String, nullable=False, default="relatorio")  # relatorio, analise, full

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
    documentos_ingeridos = relationship("DocumentoIngerido", back_populates="user")
    perfil_contador = relationship("PerfilContador", back_populates="user", uselist=False)
    vinculos_criados = relationship(
        "ContadorEmpresaVinculo",
        back_populates="criado_por",
        foreign_keys="ContadorEmpresaVinculo.criado_por_user_id",
    )
    vinculos_revogados = relationship(
        "ContadorEmpresaVinculo",
        back_populates="revogado_por",
        foreign_keys="ContadorEmpresaVinculo.revogado_por_user_id",
    )

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class PerfilContador(Base):
    """Entidade regulatória do contador parceiro — separada de User."""

    __tablename__ = "perfis_contador"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pendente', 'aprovado', 'suspenso')",
            name="ck_perfis_contador_status_valido",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("usuarios.id"), unique=True, nullable=False, index=True)

    # Identificação regulatória
    crc = Column(String(20), nullable=False, unique=True, index=True)
    uf_crc = Column(String(2), nullable=False)

    # Estado soberano
    status = Column(String(20), nullable=False, default="pendente", server_default="pendente")
    # pendente | aprovado | suspenso

    # Reputação operacional
    reputacao_score = Column(Numeric(5, 2), nullable=False, default=0, server_default="0")

    # Auditoria de aprovação
    aprovado_em = Column(DateTime, nullable=True)
    aprovado_por = Column(String(255), nullable=True)  # email do admin aprovador

    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="perfil_contador")
    homologacoes = relationship("HomologacaoDocumental", back_populates="contador")
    vinculos_empresa = relationship("ContadorEmpresaVinculo", back_populates="contador")
    atribuicoes = relationship("HomologacaoAtribuicao", back_populates="contador")


class HomologacaoDocumental(Base):
    """Homologação humana de documento ingerido por contador parceiro."""

    __tablename__ = "homologacoes_documentais"

    id = Column(Integer, primary_key=True, index=True)
    documento_ingerido_id = Column(Integer, ForeignKey("documentos_ingeridos.id"), nullable=False, index=True)
    contador_id = Column(Integer, ForeignKey("perfis_contador.id"), nullable=False, index=True)

    # Tipo e versão do parecer
    tipo_decisao = Column(String(50), nullable=False, default="homologacao_documental")
    # homologacao_documental | revisao_ocr | parecer_fiscal
    versao_parecer = Column(String(10), nullable=False, default="1.0")

    # Estado soberano
    status = Column(String(20), nullable=False, default="pendente", server_default="pendente")
    # pendente | aprovado | rejeitado

    # Parecer auditável
    parecer_texto = Column(Text, nullable=True)
    assinatura_logica = Column(String(64), nullable=True)
    # SHA-256(parecer_texto + contador_id + decidido_em) — V1 lógico

    # Timestamps
    criado_em = Column(DateTime, default=datetime.utcnow)
    decidido_em = Column(DateTime, nullable=True)

    # Relationships
    documento_ingerido = relationship("DocumentoIngerido", back_populates="homologacoes")
    contador = relationship("PerfilContador", back_populates="homologacoes")


class ContadorEmpresaVinculo(Base):
    """Vínculo soberano contador↔empresa — ADR-004 / DT-CONTADOR-01."""

    __tablename__ = "contador_empresa_vinculo"

    id = Column(Integer, primary_key=True, index=True)
    contador_id = Column(Integer, ForeignKey("perfis_contador.id"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)

    escopo_chave = Column(String(100), nullable=False)
    escopo = Column(JSON, nullable=True)

    origem = Column(String(20), nullable=False)
    # ADR-005: origem_cliente = de onde veio a relação comercial do cliente
    # Valores: contador_parceiro | plataforma_directa | empresa_directa | legado
    # INV-CARTEIRA-06: novos vínculos devem declarar explicitamente; legado só para backfill
    origem_cliente = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, default="activo", server_default="activo", index=True)
    # activo | suspenso | revogado | expirado

    criado_por_user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    criado_por_email = Column(String(255), nullable=False)
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow)
    validade = Column(DateTime, nullable=True)
    policy_version = Column(String(50), nullable=True)

    revogado_em = Column(DateTime, nullable=True)
    revogado_por_user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "origem IN ('admin', 'cliente', 'sistema')",
            name="ck_vinculo_origem_valida",
        ),
        CheckConstraint(
            "status IN ('activo', 'suspenso', 'revogado', 'expirado')",
            name="ck_vinculo_status_valido",
        ),
        CheckConstraint(
            "origem != 'sistema' OR policy_version IS NOT NULL",
            name="ck_vinculo_sistema_exige_policy",
        ),
        CheckConstraint(
            "escopo_chave = lower(escopo_chave)",
            name="ck_vinculo_escopo_chave_normalizado",
        ),
        CheckConstraint(
            "length(trim(escopo_chave)) > 0",
            name="ck_vinculo_escopo_chave_nao_vazio",
        ),
        CheckConstraint(
            "origem_cliente IN ('contador_parceiro', 'plataforma_directa', 'empresa_directa', 'legado')",
            name="ck_vinculo_origem_cliente_dominio",
        ),
    )

    contador = relationship("PerfilContador", back_populates="vinculos_empresa")
    empresa = relationship("Empresa", back_populates="vinculos_contador")
    criado_por = relationship(
        "User",
        back_populates="vinculos_criados",
        foreign_keys=[criado_por_user_id],
    )
    revogado_por = relationship(
        "User",
        back_populates="vinculos_revogados",
        foreign_keys=[revogado_por_user_id],
    )
    atribuicoes = relationship("HomologacaoAtribuicao", back_populates="vinculo")


class HomologacaoAtribuicao(Base):
    """Atribuição soberana documento↔contador — ADR-004 / DT-CONTADOR-01.

    INV-VINCULO-01: coerência empresa_id entre documento, atribuição e vínculo
    é garantida provisoriamente pela service layer (DT-CONTADOR-02).

    No fluxo DT-CONTADOR-01, HomologacaoDocumental só deve ser criada após
    HomologacaoAtribuicao com status=aceite.
    """

    __tablename__ = "homologacao_atribuicao"

    id = Column(Integer, primary_key=True, index=True)
    documento_ingerido_id = Column(
        Integer, ForeignKey("documentos_ingeridos.id"), nullable=False, index=True
    )
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    contador_id = Column(Integer, ForeignKey("perfis_contador.id"), nullable=False, index=True)
    vinculo_id = Column(
        Integer, ForeignKey("contador_empresa_vinculo.id"), nullable=False, index=True
    )

    escopo_chave = Column(String(100), nullable=False)
    escopo = Column(JSON, nullable=True)

    status = Column(String(20), nullable=False, default="atribuida", server_default="atribuida", index=True)
    # atribuida | aceite | concluida | recusada | expirada
    complexidade = Column(String(20), nullable=False)
    # baixa | media | alta
    modo_atribuicao = Column(String(20), nullable=False)
    # automatico | recomendado | manual

    policy_version = Column(String(50), nullable=True)
    regra_matching_id = Column(String(100), nullable=True)

    atribuido_em = Column(DateTime, nullable=False, default=datetime.utcnow)
    aceite_em = Column(DateTime, nullable=True)
    concluido_em = Column(DateTime, nullable=True)

    auditoria = Column(JSON, nullable=True)

    documento_ingerido = relationship("DocumentoIngerido", back_populates="atribuicoes")
    empresa = relationship("Empresa", back_populates="atribuicoes_homologacao")
    contador = relationship("PerfilContador", back_populates="atribuicoes")
    vinculo = relationship("ContadorEmpresaVinculo", back_populates="atribuicoes")


class TermosAceitacao(Base):
    __tablename__ = "termos_aceitacao"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    versao_termos = Column(String(50), nullable=False)
    aceite_em = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(45), nullable=True)


class Pagamento(Base):
    __tablename__ = "pagamentos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    plano_id = Column(Integer, ForeignKey("planos.id"), nullable=True)
    relatorio_analise_id = Column(Integer, ForeignKey("relatorios_analise.id"), nullable=True)

    # Idempotência — previne cobranças duplicadas
    idempotency_key = Column(String, unique=True, index=True, nullable=False)

    # Valores financeiros soberanos — Numeric, não Float
    valor = Column(Numeric(10, 2), nullable=False)

    # Estado interno soberano
    status = Column(String, nullable=False, default="pending")  # pending, approved, rejected, refunded
    confirmado_em = Column(DateTime, nullable=True)

    # Integração Mercado Pago — apenas referência externa
    mp_payment_id = Column(String, unique=True, index=True, nullable=True)
    mp_status_raw = Column(String, nullable=True)  # resposta bruta para auditoria
    payment_method_id = Column(String, nullable=False, default="pix")
    qr_code = Column(String, nullable=True)
    qr_code_base64 = Column(String, nullable=True)

    # Metadados soberanos do gateway (checkout, boleto, payload auditável)
    checkout_url = Column(String, nullable=True)
    checkout_expires_at = Column(DateTime, nullable=True)
    gateway_provider = Column(String, nullable=True, server_default="mercadopago")
    gateway_payment_type = Column(String, nullable=True)
    gateway_external_reference = Column(String, nullable=True)
    boleto_url = Column(String, nullable=True)
    boleto_barcode = Column(String, nullable=True)
    gateway_payload = Column(JSON, nullable=True)

    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tentativas = relationship("PagamentoTentativa", back_populates="pagamento")


class PagamentoTentativa(Base):
    """Ledger operacional de tentativas de cobrança por pagamento (auditável)."""

    __tablename__ = "pagamento_tentativas"

    id = Column(Integer, primary_key=True)
    pagamento_id = Column(Integer, ForeignKey("pagamentos.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)

    gateway_provider = Column(String, nullable=False, index=True)
    payment_type = Column(String, nullable=False)
    status = Column(String, nullable=False, index=True)
    error_code = Column(String, nullable=True, index=True)
    error_message = Column(String, nullable=True)
    error_origin = Column(String, nullable=True)
    http_status = Column(Integer, nullable=True)

    request_payload = Column(JSON, nullable=True)
    response_payload = Column(JSON, nullable=True)

    started_at = Column(DateTime, nullable=False, server_default=func.now())
    finished_at = Column(DateTime, nullable=True)

    pagamento = relationship("Pagamento", back_populates="tentativas")
    user = relationship("User")


class ConsentimentoLGPD(Base):
    __tablename__ = "consentimentos_lgpd"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    versao_politica = Column(String(50), nullable=False)
    finalidade = Column(String(200), nullable=False)
    consentiu = Column(Boolean, nullable=False)
    consentiu_em = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(45), nullable=True)


# Regimes tributários esperados pelo regime_router (fluxo BLOCO 10)
# empresa → regime_tributario → regime_router → engine tributário correto
REGIMES_TRIBUTARIOS = ("simples", "presumido", "real", "mei")


# =========================
# EMPRESA
# =========================
class Empresa(Base):
    __tablename__ = "empresas"

    __table_args__ = (
        CheckConstraint(
            "status_empresa IN ('ativa', 'em_abertura', 'suspensa', 'encerrada')",
            name="ck_empresas_status_valido",
        ),
        CheckConstraint(
            "porte IN ('mei', 'me', 'epp', 'medio', 'grande')",
            name="ck_empresas_porte_valido",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    cnpj = Column(String, nullable=True)
    razao_social = Column(String, nullable=True)
    regime_tributario = Column(String, nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("usuarios.id"))

    # Núcleo Empresarial V1
    cnae_principal = Column(String(10), nullable=True, index=True)
    cnae_secundarios = Column(JSON, nullable=True)
    municipio = Column(String(100), nullable=True)
    uf = Column(String(2), nullable=True, index=True)
    porte = Column(String(20), nullable=True, index=True)
    status_empresa = Column(String(20), nullable=True, default="ativa", server_default="ativa", index=True)
    data_abertura = Column(Date, nullable=True)
    capital_social = Column(Numeric(15, 2), nullable=True)
    optante_simples = Column(Boolean, nullable=True, default=False)
    optante_mei = Column(Boolean, nullable=True, default=False)

    # Inputs para cálculo Fator R — nunca guardar o ratio derivado
    faturamento_anual = Column(Numeric(15, 2), nullable=True)
    folha_anual = Column(Numeric(15, 2), nullable=True)
    # fator_r = folha_anual / faturamento_anual — calculado pelo motor fiscal

    owner = relationship("User", back_populates="empresas")
    documentos_fiscais = relationship("DocumentoFiscal", back_populates="empresa")
    documentos_ingeridos = relationship("DocumentoIngerido", back_populates="empresa")
    vinculos_contador = relationship("ContadorEmpresaVinculo", back_populates="empresa")
    atribuicoes_homologacao = relationship("HomologacaoAtribuicao", back_populates="empresa")


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
    nivel_confianca_fonte = Column(String(40), nullable=True)
    # nivel_confianca_fonte: "oficial" | "candidata_oficial" | "convenio_base" |
    #                        "convenio_base_sem_aliquota" | "estimativa" | "sem_fonte"
    url_fonte = Column(String(1000), nullable=True)  # link oficial quando disponível
    importado_em = Column(DateTime, default=func.now(), nullable=True)
    importado_por = Column(String(100), nullable=True)  # ex: "importar_mva_pa.py v1.0"


# =========================
# TABELA PMPF (preço máximo ao consumidor final — base ST em UF que adotam PMPF)
# =========================
class TabelaPMPF(Base):
    __tablename__ = "tabela_pmpf"
    __table_args__ = (
        UniqueConstraint(
            "estado",
            "ncm",
            "marca",
            "embalagem_ml",
            "vigencia_inicio",
            name="uq_pmpf_estado_ncm_marca_embalagem_vigencia",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    estado = Column(String(2), nullable=False, index=True)
    ncm = Column(String(20), nullable=False, index=True)
    cest = Column(String(9), nullable=True)
    marca = Column(String(200), nullable=False)
    embalagem_ml = Column(Integer, nullable=True)
    pmpf_reais = Column(Float, nullable=False)
    aliquota_interna = Column(Float, nullable=False)
    vigencia_inicio = Column(Date, nullable=False)
    vigencia_fim = Column(Date, nullable=True)
    fonte_legal = Column(String(500), nullable=True)
    url_fonte = Column(String(1000), nullable=True)
    nivel_confianca_fonte = Column(String(40), nullable=True)
    # nivel_confianca_fonte: "oficial" | "candidata_oficial" | "convenio_base" |
    #                        "convenio_base_sem_aliquota" | "estimativa" | "sem_fonte"
    importado_por = Column(String(100), nullable=True)
    importado_em = Column(DateTime, default=func.now(), nullable=True)
    criado_em = Column(DateTime, default=func.now(), nullable=False)


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
    processado = Column(Boolean, default=False, nullable=False, server_default="false")
    processado_em = Column(DateTime, nullable=True)
    processado_por = Column(String(100), nullable=True)
    notas_resolucao = Column(String(1000), nullable=True)


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
    __table_args__ = (
        UniqueConstraint(
            "empresa_id",
            "xml_chave",
            "analysis_type",
            name="uq_relatorios_analise_empresa_xml_tipo",
        ),
    )

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
# DOCUMENTO INGERIDO (pipeline documental — evidência persistida)
# Alinhado a app.services.document_ingestion.audit.EvidenciaDocumental
# =========================
class DocumentoIngerido(Base):
    __tablename__ = "documentos_ingeridos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=True, index=True)

    conteudo_sha256 = Column(String(64), nullable=False, index=True)
    evidencia_em = Column(DateTime, nullable=False, default=datetime.utcnow)
    versao_pipeline = Column(String(32), nullable=False)
    tipo_documento = Column(String(32), nullable=False, index=True)
    score_confianca = Column(Float, nullable=False)
    decisao = Column(String(32), nullable=False, index=True)
    requereu_ocr = Column(Boolean, nullable=False, default=False, server_default="false")

    campos_extraidos = Column(JSON, nullable=True)
    campos_estruturados = Column(JSON, nullable=True)  # DT-DOC-01 — CT-DOC-001 §3
    campos_nao_extraidos = Column(JSON, nullable=True)
    motivos = Column(JSON, nullable=True)

    validado_humano = Column(Boolean, nullable=False, default=False, server_default="false")
    validado_por = Column(String(255), nullable=True)
    validado_em = Column(DateTime, nullable=True)

    nome_ficheiro = Column(String(512), nullable=True)
    tamanho_bytes = Column(Integer, nullable=False, default=0)

    user = relationship("User", back_populates="documentos_ingeridos")
    empresa = relationship("Empresa", back_populates="documentos_ingeridos")
    homologacoes = relationship("HomologacaoDocumental", back_populates="documento_ingerido")
    atribuicoes = relationship("HomologacaoAtribuicao", back_populates="documento_ingerido")


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

# =========================
# ADR-020 V0.3 R2 - ACQUISITION FOUNDATION (IMPLEMENTATION R3)
# =========================
import hashlib
import re


_ADR020_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_ADR020_CAS_LOCATION_PATTERN = re.compile(
    r"^cas\+sha256://([0-9a-f]{64})/([1-9][0-9]*)$"
)

_ARTIFACT_REFERENCE_EVENTS = (
    "identificada",
    "agendada",
    "resolvida",
    "nao_resolvida",
)

_ACQUISITION_EVENT_STATE = {
    "criacao": "planeada",
    "inicio": "em_execucao",
    "conclusao": "concluida",
    "conclusao_parcial": "concluida_parcial",
    "indisponibilidade": "indisponivel",
    "falha": "falhada",
    "interrupcao": "interrompida",
    "cancelamento": "cancelada",
}

_ACQUISITION_TERMINAL_STATES = {
    "concluida",
    "concluida_parcial",
    "indisponivel",
    "falhada",
    "interrompida",
    "cancelada",
}

_VERIFICATION_TYPES = (
    "authenticity",
    "integrity",
    "preservation",
)

_VERIFICATION_OUTCOMES = (
    "conclusivo_favoravel",
    "conclusivo_desfavoravel",
    "inconclusivo",
)


def _adr020_require_sha256(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _ADR020_HASH_PATTERN.fullmatch(value):
        raise ValueError(
            f"ADR-020 {field_name} must be a lowercase SHA-256 hexadecimal digest"
        )


def _adr020_require_canonical_cas_location(
    value: str,
    artifact_hash: str,
    byte_size: int,
) -> None:
    if not isinstance(value, str):
        raise ValueError(
            "ADR-020 immutable_location must use canonical "
            "cas+sha256://<hash>/<byte_size> form"
        )
    match = _ADR020_CAS_LOCATION_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(
            "ADR-020 immutable_location must use canonical "
            "cas+sha256://<hash>/<byte_size> form"
        )
    location_hash, location_size = match.groups()
    if location_hash != artifact_hash or int(location_size) != byte_size:
        raise ValueError(
            "ADR-020 immutable_location identity must match artifact_hash and byte_size"
        )


class ArtifactReference(Base):
    """One immutable event in an ArtifactReference projection chain."""

    __tablename__ = "artifact_references"
    __table_args__ = (
        UniqueConstraint(
            "artifact_reference_id",
            "event_sequence",
            name="uq_artifact_references_identity_sequence",
        ),
        UniqueConstraint(
            "artifact_reference_record_id",
            "artifact_reference_id",
            name="uq_artifact_references_record_identity",
        ),
        ForeignKeyConstraint(
            [
                "previous_artifact_reference_record_id",
                "artifact_reference_id",
            ],
            [
                "artifact_references.artifact_reference_record_id",
                "artifact_references.artifact_reference_id",
            ],
            name="fk_artifact_references_previous_same_identity",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "record_hash",
            name="uq_artifact_references_record_hash",
        ),
        CheckConstraint(
            "reference_event IN "
            "('identificada', 'agendada', 'resolvida', 'nao_resolvida')",
            name="ck_artifact_references_event_valid",
        ),
        CheckConstraint(
            "event_sequence > 0",
            name="ck_artifact_references_sequence_positive",
        ),
        CheckConstraint(
            "(event_sequence = 1 "
            "AND reference_event = 'identificada' "
            "AND previous_artifact_reference_record_id IS NULL) "
            "OR (event_sequence > 1 "
            "AND previous_artifact_reference_record_id IS NOT NULL)",
            name="ck_artifact_references_initial_or_predecessor",
        ),
        CheckConstraint(
            "previous_artifact_reference_record_id IS NULL "
            "OR previous_artifact_reference_record_id "
            "<> artifact_reference_record_id",
            name="ck_artifact_references_no_self_reference",
        ),
        CheckConstraint(
            "length(trim(source_id)) > 0",
            name="ck_artifact_references_source_id_not_empty",
        ),
        CheckConstraint(
            "length(trim(exact_locator)) > 0",
            name="ck_artifact_references_locator_not_empty",
        ),
        CheckConstraint(
            "length(record_hash) = 64",
            name="ck_artifact_references_record_hash_len",
        ),
    )

    artifact_reference_record_id = Column(String(64), primary_key=True)
    artifact_reference_id = Column(String(64), nullable=False, index=True)
    reference_event = Column(String(32), nullable=False, index=True)
    event_sequence = Column(Integer, nullable=False)
    previous_artifact_reference_record_id = Column(String(64), nullable=True)
    source_id = Column(String(255), nullable=False, index=True)
    exact_locator = Column(Text, nullable=False)
    official_identifier = Column(String(255), nullable=True, index=True)
    expected_media_type = Column(String(255), nullable=True)
    discovered_at = Column(DateTime(timezone=True), nullable=False)
    occurred_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    evidence = Column(JSON, nullable=False)
    record_hash = Column(String(64), nullable=False)


class AcquisitionExecution(Base):
    """One immutable event in one exact technical acquisition attempt."""

    __tablename__ = "acquisition_executions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["artifact_reference_record_id", "artifact_reference_id"],
            [
                "artifact_references.artifact_reference_record_id",
                "artifact_references.artifact_reference_id",
            ],
            name="fk_acquisition_executions_exact_reference",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "acquisition_execution_id",
            "event_sequence",
            name="uq_acquisition_executions_identity_sequence",
        ),
        UniqueConstraint(
            "artifact_reference_id",
            "attempt_number",
            "event_sequence",
            name="uq_acquisition_executions_reference_attempt_sequence",
        ),
        UniqueConstraint(
            "acquisition_execution_record_id",
            "acquisition_execution_id",
            "artifact_reference_id",
            "attempt_number",
            name="uq_acquisition_executions_record_attempt",
        ),
        UniqueConstraint(
            "acquisition_execution_record_id",
            "acquisition_execution_id",
            "artifact_reference_id",
            "attempt_number",
            "execution_event",
            "projected_state",
            name="uq_acquisition_executions_exact_projection",
        ),
        ForeignKeyConstraint(
            [
                "previous_acquisition_execution_record_id",
                "acquisition_execution_id",
                "artifact_reference_id",
                "attempt_number",
            ],
            [
                "acquisition_executions.acquisition_execution_record_id",
                "acquisition_executions.acquisition_execution_id",
                "acquisition_executions.artifact_reference_id",
                "acquisition_executions.attempt_number",
            ],
            name="fk_acquisition_executions_previous_same_attempt",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "record_hash",
            name="uq_acquisition_executions_record_hash",
        ),
        CheckConstraint(
            "execution_event IN "
            "('criacao', 'inicio', 'conclusao', 'conclusao_parcial', "
            "'indisponibilidade', 'falha', 'interrupcao', 'cancelamento')",
            name="ck_acquisition_executions_event_valid",
        ),
        CheckConstraint(
            "projected_state IN "
            "('planeada', 'em_execucao', 'concluida', 'concluida_parcial', "
            "'indisponivel', 'falhada', 'interrompida', 'cancelada')",
            name="ck_acquisition_executions_state_valid",
        ),
        CheckConstraint(
            "(execution_event = 'criacao' AND projected_state = 'planeada') "
            "OR (execution_event = 'inicio' AND projected_state = 'em_execucao') "
            "OR (execution_event = 'conclusao' AND projected_state = 'concluida') "
            "OR (execution_event = 'conclusao_parcial' "
            "AND projected_state = 'concluida_parcial') "
            "OR (execution_event = 'indisponibilidade' "
            "AND projected_state = 'indisponivel') "
            "OR (execution_event = 'falha' AND projected_state = 'falhada') "
            "OR (execution_event = 'interrupcao' "
            "AND projected_state = 'interrompida') "
            "OR (execution_event = 'cancelamento' "
            "AND projected_state = 'cancelada')",
            name="ck_acquisition_executions_event_state_pair",
        ),
        CheckConstraint(
            "attempt_number > 0",
            name="ck_acquisition_executions_attempt_positive",
        ),
        CheckConstraint(
            "event_sequence > 0",
            name="ck_acquisition_executions_sequence_positive",
        ),
        CheckConstraint(
            "(event_sequence = 1 "
            "AND execution_event = 'criacao' "
            "AND projected_state = 'planeada' "
            "AND previous_acquisition_execution_record_id IS NULL) "
            "OR (event_sequence > 1 "
            "AND previous_acquisition_execution_record_id IS NOT NULL)",
            name="ck_acquisition_executions_initial_or_predecessor",
        ),
        CheckConstraint(
            "previous_acquisition_execution_record_id IS NULL "
            "OR previous_acquisition_execution_record_id "
            "<> acquisition_execution_record_id",
            name="ck_acquisition_executions_no_self_reference",
        ),
        CheckConstraint(
            "length(trim(actor_or_worker)) > 0",
            name="ck_acquisition_executions_actor_not_empty",
        ),
        CheckConstraint(
            "length(trim(adapter_version)) > 0",
            name="ck_acquisition_executions_adapter_not_empty",
        ),
        CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL "
            "OR finished_at >= started_at",
            name="ck_acquisition_executions_time_order",
        ),
        CheckConstraint(
            "length(record_hash) = 64",
            name="ck_acquisition_executions_record_hash_len",
        ),
    )

    acquisition_execution_record_id = Column(String(64), primary_key=True)
    acquisition_execution_id = Column(String(64), nullable=False, index=True)
    artifact_reference_record_id = Column(String(64), nullable=False)
    artifact_reference_id = Column(String(64), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)
    execution_event = Column(String(32), nullable=False, index=True)
    projected_state = Column(String(32), nullable=False, index=True)
    event_sequence = Column(Integer, nullable=False)
    previous_acquisition_execution_record_id = Column(String(64), nullable=True)
    actor_or_worker = Column(String(255), nullable=False)
    adapter_version = Column(String(128), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    occurred_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    structured_result = Column(JSON, nullable=True)
    structured_error = Column(JSON, nullable=True)
    evidence = Column(JSON, nullable=False)
    provenance = Column(JSON, nullable=False)
    record_hash = Column(String(64), nullable=False)


class NormativeArtifact(Base):
    """Immutable normative bytes or a content-addressed immutable location."""

    __tablename__ = "normative_artifacts"
    __table_args__ = (
        ForeignKeyConstraint(
            [
                "acquisition_execution_record_id",
                "acquisition_execution_id",
                "artifact_reference_id",
                "acquisition_attempt_number",
                "acquisition_event",
                "acquisition_state",
            ],
            [
                "acquisition_executions.acquisition_execution_record_id",
                "acquisition_executions.acquisition_execution_id",
                "acquisition_executions.artifact_reference_id",
                "acquisition_executions.attempt_number",
                "acquisition_executions.execution_event",
                "acquisition_executions.projected_state",
            ],
            name="fk_normative_artifacts_completed_execution",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "normative_artifact_id",
            "artifact_hash",
            name="uq_normative_artifacts_identity_hash",
        ),
        UniqueConstraint(
            "acquisition_execution_record_id",
            name="uq_normative_artifacts_single_per_acquisition_completion",
        ),
        UniqueConstraint(
            "record_hash",
            name="uq_normative_artifacts_record_hash",
        ),
        CheckConstraint(
            "acquisition_event = 'conclusao' "
            "AND acquisition_state = 'concluida'",
            name="ck_normative_artifacts_completed_acquisition",
        ),
        CheckConstraint(
            "(immutable_bytes IS NOT NULL AND immutable_location IS NULL) "
            "OR (immutable_bytes IS NULL AND immutable_location IS NOT NULL)",
            name="ck_normative_artifacts_exactly_one_storage",
        ),
        CheckConstraint(
            "immutable_location IS NULL "
            "OR length(trim(immutable_location)) > 0",
            name="ck_normative_artifacts_location_not_empty",
        ),
        CheckConstraint(
            "byte_size > 0",
            name="ck_normative_artifacts_byte_size_positive",
        ),
        CheckConstraint(
            "length(trim(media_type)) > 0",
            name="ck_normative_artifacts_media_type_not_empty",
        ),
        CheckConstraint(
            "length(artifact_hash) = 64",
            name="ck_normative_artifacts_artifact_hash_len",
        ),
        CheckConstraint(
            "length(record_hash) = 64",
            name="ck_normative_artifacts_record_hash_len",
        ),
    )

    normative_artifact_id = Column(String(64), primary_key=True)
    acquisition_execution_record_id = Column(String(64), nullable=False)
    acquisition_execution_id = Column(String(64), nullable=False, index=True)
    artifact_reference_id = Column(String(64), nullable=False, index=True)
    acquisition_attempt_number = Column(Integer, nullable=False)
    acquisition_event = Column(
        String(32),
        nullable=False,
        default="conclusao",
        server_default="conclusao",
    )
    acquisition_state = Column(
        String(32),
        nullable=False,
        default="concluida",
        server_default="concluida",
    )
    immutable_bytes = Column(LargeBinary, nullable=True)
    immutable_location = Column(Text, nullable=True)
    byte_size = Column(Integer, nullable=False)
    artifact_hash = Column(String(64), nullable=False, index=True)
    acquired_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    media_type = Column(String(255), nullable=False)
    provenance = Column(JSON, nullable=False)
    record_hash = Column(String(64), nullable=False)


class ArtifactVerificationRecord(Base):
    """Immutable verification record bound to exact bytes and predecessor gates."""

    __tablename__ = "artifact_verification_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["normative_artifact_id", "verified_artifact_hash"],
            [
                "normative_artifacts.normative_artifact_id",
                "normative_artifacts.artifact_hash",
            ],
            name="fk_artifact_verifications_artifact_hash",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "artifact_verification_record_id",
            "normative_artifact_id",
            "verified_artifact_hash",
            name="uq_artifact_verifications_identity_artifact",
        ),
        UniqueConstraint(
            "artifact_verification_record_id",
            "normative_artifact_id",
            "verified_artifact_hash",
            "verification_type",
            "outcome",
            name="uq_artifact_verifications_exact_result",
        ),
        ForeignKeyConstraint(
            [
                "previous_verification_record_id",
                "normative_artifact_id",
                "verified_artifact_hash",
            ],
            [
                "artifact_verification_records.artifact_verification_record_id",
                "artifact_verification_records.normative_artifact_id",
                "artifact_verification_records.verified_artifact_hash",
            ],
            name="fk_artifact_verifications_previous_same_artifact",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "authenticity_verification_record_id",
                "normative_artifact_id",
                "verified_artifact_hash",
                "authenticity_predecessor_type",
                "authenticity_predecessor_outcome",
            ],
            [
                "artifact_verification_records.artifact_verification_record_id",
                "artifact_verification_records.normative_artifact_id",
                "artifact_verification_records.verified_artifact_hash",
                "artifact_verification_records.verification_type",
                "artifact_verification_records.outcome",
            ],
            name="fk_artifact_verifications_authenticity_favorable",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "integrity_verification_record_id",
                "normative_artifact_id",
                "verified_artifact_hash",
                "integrity_predecessor_type",
                "integrity_predecessor_outcome",
            ],
            [
                "artifact_verification_records.artifact_verification_record_id",
                "artifact_verification_records.normative_artifact_id",
                "artifact_verification_records.verified_artifact_hash",
                "artifact_verification_records.verification_type",
                "artifact_verification_records.outcome",
            ],
            name="fk_artifact_verifications_integrity_favorable",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "record_hash",
            name="uq_artifact_verifications_record_hash",
        ),
        CheckConstraint(
            "verification_type IN ('authenticity', 'integrity', 'preservation')",
            name="ck_artifact_verifications_type_valid",
        ),
        CheckConstraint(
            "outcome IN "
            "('conclusivo_favoravel', 'conclusivo_desfavoravel', 'inconclusivo')",
            name="ck_artifact_verifications_outcome_valid",
        ),
        CheckConstraint(
            "(verification_type = 'authenticity' "
            "AND authenticity_verification_record_id IS NULL "
            "AND integrity_verification_record_id IS NULL) "
            "OR (verification_type = 'integrity' "
            "AND authenticity_verification_record_id IS NOT NULL "
            "AND integrity_verification_record_id IS NULL "
            "AND previous_verification_record_id "
            "= authenticity_verification_record_id) "
            "OR (verification_type = 'preservation' "
            "AND authenticity_verification_record_id IS NOT NULL "
            "AND integrity_verification_record_id IS NOT NULL "
            "AND previous_verification_record_id "
            "= integrity_verification_record_id)",
            name="ck_artifact_verifications_cumulative_predecessors",
        ),
        CheckConstraint(
            "(authenticity_verification_record_id IS NULL "
            "AND authenticity_predecessor_type IS NULL "
            "AND authenticity_predecessor_outcome IS NULL) "
            "OR (authenticity_verification_record_id IS NOT NULL "
            "AND authenticity_predecessor_type = 'authenticity' "
            "AND authenticity_predecessor_outcome = 'conclusivo_favoravel')",
            name="ck_artifact_verifications_authenticity_constants",
        ),
        CheckConstraint(
            "(integrity_verification_record_id IS NULL "
            "AND integrity_predecessor_type IS NULL "
            "AND integrity_predecessor_outcome IS NULL) "
            "OR (integrity_verification_record_id IS NOT NULL "
            "AND integrity_predecessor_type = 'integrity' "
            "AND integrity_predecessor_outcome = 'conclusivo_favoravel')",
            name="ck_artifact_verifications_integrity_constants",
        ),
        CheckConstraint(
            "previous_verification_record_id IS NULL "
            "OR previous_verification_record_id "
            "<> artifact_verification_record_id",
            name="ck_artifact_verifications_no_self_reference",
        ),
        CheckConstraint(
            "length(trim(verifier)) > 0",
            name="ck_artifact_verifications_verifier_not_empty",
        ),
        CheckConstraint(
            "length(trim(verifier_version)) > 0",
            name="ck_artifact_verifications_verifier_version_not_empty",
        ),
        CheckConstraint(
            "length(verified_artifact_hash) = 64",
            name="ck_artifact_verifications_artifact_hash_len",
        ),
        CheckConstraint(
            "length(record_hash) = 64",
            name="ck_artifact_verifications_record_hash_len",
        ),
    )

    artifact_verification_record_id = Column(String(64), primary_key=True)
    normative_artifact_id = Column(String(64), nullable=False, index=True)
    verified_artifact_hash = Column(String(64), nullable=False)
    verification_type = Column(String(32), nullable=False, index=True)
    outcome = Column(String(32), nullable=False, index=True)
    verifier = Column(String(255), nullable=False)
    verifier_version = Column(String(128), nullable=False)
    evidence = Column(JSON, nullable=False)
    incident_id = Column(String(64), nullable=True)
    previous_verification_record_id = Column(String(64), nullable=True)
    authenticity_verification_record_id = Column(String(64), nullable=True)
    authenticity_predecessor_type = Column(String(32), nullable=True)
    authenticity_predecessor_outcome = Column(String(32), nullable=True)
    integrity_verification_record_id = Column(String(64), nullable=True)
    integrity_predecessor_type = Column(String(32), nullable=True)
    integrity_predecessor_outcome = Column(String(32), nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    record_hash = Column(String(64), nullable=False)


def _adr020_validate_artifact_reference_insert(mapper, connection, target) -> None:
    _adr020_require_sha256(target.record_hash, "record_hash")
    if target.reference_event not in _ARTIFACT_REFERENCE_EVENTS:
        raise ValueError("ADR-020 invalid ArtifactReference event")
    if target.event_sequence <= 0:
        raise ValueError("ADR-020 ArtifactReference event_sequence must be positive")
    if target.event_sequence == 1:
        if target.reference_event != "identificada":
            raise ValueError("ADR-020 first ArtifactReference event must be identificada")
        if target.previous_artifact_reference_record_id is not None:
            raise ValueError("ADR-020 first ArtifactReference event has no predecessor")
    elif target.previous_artifact_reference_record_id is None:
        raise ValueError("ADR-020 later ArtifactReference event requires predecessor")


def _adr020_validate_acquisition_execution_insert(
    mapper,
    connection,
    target,
) -> None:
    _adr020_require_sha256(target.record_hash, "record_hash")
    expected_state = _ACQUISITION_EVENT_STATE.get(target.execution_event)
    if expected_state is None or expected_state != target.projected_state:
        raise ValueError("ADR-020 acquisition event/state pair is invalid")
    if target.attempt_number <= 0 or target.event_sequence <= 0:
        raise ValueError("ADR-020 acquisition attempt and sequence must be positive")
    if target.event_sequence == 1:
        if target.execution_event != "criacao" or target.projected_state != "planeada":
            raise ValueError("ADR-020 first acquisition event must create planeada")
        if target.previous_acquisition_execution_record_id is not None:
            raise ValueError("ADR-020 first acquisition event has no predecessor")
    elif target.previous_acquisition_execution_record_id is None:
        raise ValueError("ADR-020 later acquisition event requires predecessor")

    if target.projected_state == "planeada":
        if target.started_at is not None or target.finished_at is not None:
            raise ValueError("ADR-020 planeada cannot contain execution timestamps")
    elif target.projected_state == "em_execucao":
        if target.started_at is None or target.finished_at is not None:
            raise ValueError("ADR-020 em_execucao requires started_at and no finished_at")
    elif target.projected_state == "concluida":
        if target.started_at is None or target.finished_at is None:
            raise ValueError("ADR-020 concluida requires started_at and finished_at")
        if target.finished_at < target.started_at:
            raise ValueError("ADR-020 acquisition finished_at cannot precede started_at")
        if not isinstance(target.structured_result, dict):
            raise ValueError("ADR-020 concluida requires structured_result")
        if target.structured_result.get("bytes_received") is not True:
            raise ValueError("ADR-020 concluida requires bytes_received=true")
        byte_size = target.structured_result.get("byte_size")
        artifact_hash = target.structured_result.get("artifact_hash")
        if not isinstance(byte_size, int) or byte_size <= 0:
            raise ValueError("ADR-020 concluida requires positive byte_size")
        _adr020_require_sha256(artifact_hash, "structured_result.artifact_hash")
    elif target.projected_state in _ACQUISITION_TERMINAL_STATES:
        if target.finished_at is None:
            raise ValueError("ADR-020 terminal acquisition event requires finished_at")
        if target.started_at is not None and target.finished_at < target.started_at:
            raise ValueError("ADR-020 acquisition finished_at cannot precede started_at")


def _adr020_validate_normative_artifact_insert(mapper, connection, target) -> None:
    _adr020_require_sha256(target.artifact_hash, "artifact_hash")
    _adr020_require_sha256(target.record_hash, "record_hash")

    has_bytes = target.immutable_bytes is not None
    has_location = target.immutable_location is not None
    if has_bytes == has_location:
        raise ValueError(
            "ADR-020 NormativeArtifact requires exactly one immutable storage form"
        )
    if target.byte_size <= 0:
        raise ValueError("ADR-020 NormativeArtifact byte_size must be positive")

    if has_bytes:
        actual_size = len(target.immutable_bytes)
        actual_hash = hashlib.sha256(target.immutable_bytes).hexdigest()
        if actual_size != target.byte_size:
            raise ValueError("ADR-020 byte_size does not match immutable_bytes")
        if actual_hash != target.artifact_hash:
            raise ValueError("ADR-020 artifact_hash does not match immutable_bytes")
    else:
        _adr020_require_canonical_cas_location(
            target.immutable_location,
            target.artifact_hash,
            target.byte_size,
        )

    if target.acquisition_event != "conclusao" or target.acquisition_state != "concluida":
        raise ValueError("ADR-020 artifact requires exact concluded acquisition event")


def _adr020_validate_verification_insert(mapper, connection, target) -> None:
    _adr020_require_sha256(target.verified_artifact_hash, "verified_artifact_hash")
    _adr020_require_sha256(target.record_hash, "record_hash")
    if target.verification_type not in _VERIFICATION_TYPES:
        raise ValueError("ADR-020 invalid verification_type")
    if target.outcome not in _VERIFICATION_OUTCOMES:
        raise ValueError("ADR-020 invalid verification outcome")

    if target.verification_type == "authenticity":
        if (
            target.authenticity_verification_record_id is not None
            or target.authenticity_predecessor_type is not None
            or target.authenticity_predecessor_outcome is not None
            or target.integrity_verification_record_id is not None
            or target.integrity_predecessor_type is not None
            or target.integrity_predecessor_outcome is not None
        ):
            raise ValueError("ADR-020 authenticity cannot depend on later gates")
    elif target.verification_type == "integrity":
        if target.authenticity_verification_record_id is None:
            raise ValueError("ADR-020 integrity requires favorable authenticity")
        if (
            target.authenticity_predecessor_type != "authenticity"
            or target.authenticity_predecessor_outcome
            != "conclusivo_favoravel"
        ):
            raise ValueError("ADR-020 integrity requires exact favorable authenticity")
        if (
            target.integrity_verification_record_id is not None
            or target.integrity_predecessor_type is not None
            or target.integrity_predecessor_outcome is not None
        ):
            raise ValueError("ADR-020 integrity cannot depend on integrity predecessor")
        if (
            target.previous_verification_record_id
            != target.authenticity_verification_record_id
        ):
            raise ValueError("ADR-020 integrity predecessor must be authenticity")
    else:
        if (
            target.authenticity_verification_record_id is None
            or target.integrity_verification_record_id is None
        ):
            raise ValueError(
                "ADR-020 preservation requires favorable authenticity and integrity"
            )
        if (
            target.authenticity_predecessor_type != "authenticity"
            or target.authenticity_predecessor_outcome
            != "conclusivo_favoravel"
            or target.integrity_predecessor_type != "integrity"
            or target.integrity_predecessor_outcome
            != "conclusivo_favoravel"
        ):
            raise ValueError("ADR-020 preservation requires exact favorable gates")
        if (
            target.previous_verification_record_id
            != target.integrity_verification_record_id
        ):
            raise ValueError("ADR-020 preservation predecessor must be integrity")


def _adr020_reject_append_only_mutation(mapper, connection, target) -> None:
    raise RuntimeError(
        "ADR-020 append-only violation: update/delete is forbidden for "
        f"{target.__class__.__name__}"
    )


_ADR020_INSERT_VALIDATORS = {
    ArtifactReference: _adr020_validate_artifact_reference_insert,
    AcquisitionExecution: _adr020_validate_acquisition_execution_insert,
    NormativeArtifact: _adr020_validate_normative_artifact_insert,
    ArtifactVerificationRecord: _adr020_validate_verification_insert,
}

for _adr020_append_only_model, _adr020_insert_validator in (
    _ADR020_INSERT_VALIDATORS.items()
):
    event.listen(
        _adr020_append_only_model,
        "before_insert",
        _adr020_insert_validator,
    )
    event.listen(
        _adr020_append_only_model,
        "before_update",
        _adr020_reject_append_only_mutation,
    )
    event.listen(
        _adr020_append_only_model,
        "before_delete",
        _adr020_reject_append_only_mutation,
    )

del _adr020_append_only_model
del _adr020_insert_validator

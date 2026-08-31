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
    ordem_checkout_id = Column(
        Integer,
        ForeignKey("ordens_checkout.id"),
        nullable=True,
        unique=True,
    )

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
# CHECKOUT DURAVEL
# =========================
class OrdemCheckout(Base):
    __tablename__ = "ordens_checkout"
    __table_args__ = (
        CheckConstraint(
            "moeda = 'BRL'",
            name="ck_ordens_checkout_moeda_brl",
        ),
        CheckConstraint(
            "estado IN ('pending', 'paid', 'cancelled')",
            name="ck_ordens_checkout_estado_valido",
        ),
        CheckConstraint(
            "valor > 0",
            name="ck_ordens_checkout_valor_positivo",
        ),
        CheckConstraint(
            "(offer_id IS NULL AND plano_id IS NOT NULL AND empresa_id IS NOT NULL "
            "AND offer_code IS NULL AND contract_version IS NULL AND vertical IS NULL "
            "AND commercial_model IS NULL AND subject_type IS NULL AND subject_id IS NULL "
            "AND billing_period IS NULL AND usage_unit IS NULL AND usage_limit IS NULL) "
            "OR (offer_id IS NOT NULL AND plano_id IS NULL AND offer_code IS NOT NULL "
            "AND contract_version IS NOT NULL AND vertical IS NOT NULL "
            "AND commercial_model IS NOT NULL AND subject_type IS NOT NULL "
            "AND subject_id IS NOT NULL)",
            name="ck_ordens_checkout_formato_coerente",
        ),
        CheckConstraint(
            "offer_id IS NULL OR commercial_model IN ('monthly', 'one_time')",
            name="ck_ordens_checkout_offer_commercial_model",
        ),
        CheckConstraint(
            "offer_id IS NULL OR vertical IN ('tax', 'document')",
            name="ck_ordens_checkout_offer_vertical",
        ),
        CheckConstraint(
            "offer_id IS NULL OR subject_type IN ('cpf', 'company', 'institution')",
            name="ck_ordens_checkout_offer_subject_type",
        ),
        CheckConstraint(
            "offer_id IS NULL OR (contract_version > 0 AND subject_id > 0)",
            name="ck_ordens_checkout_offer_identidade_positiva",
        ),
        CheckConstraint(
            "offer_id IS NULL OR subject_type <> 'company' "
            "OR (empresa_id IS NOT NULL AND subject_id = empresa_id)",
            name="ck_ordens_checkout_offer_company_coerente",
        ),
        CheckConstraint(
            "offer_id IS NULL OR commercial_model <> 'monthly' "
            "OR (billing_period = 'month' AND usage_unit IS NULL AND usage_limit IS NULL)",
            name="ck_ordens_checkout_offer_monthly_coerente",
        ),
        CheckConstraint(
            "offer_id IS NULL OR commercial_model <> 'one_time' "
            "OR (billing_period IS NULL AND usage_unit IS NOT NULL "
            "AND length(trim(usage_unit)) > 0 AND usage_limit > 0)",
            name="ck_ordens_checkout_offer_one_time_coerente",
        ),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=True, index=True)
    plano_id = Column(Integer, ForeignKey("planos.id"), nullable=True, index=True)
    offer_id = Column(Integer, ForeignKey("checkout_offers.id"), nullable=True, index=True)
    offer_code = Column(String(120), nullable=True)
    contract_version = Column(Integer, nullable=True)
    vertical = Column(String(20), nullable=True)
    commercial_model = Column(String(20), nullable=True)
    subject_type = Column(String(20), nullable=True)
    subject_id = Column(Integer, nullable=True)
    valor = Column(Numeric(10, 2), nullable=False)
    moeda = Column(String(3), nullable=False, default="BRL", server_default="BRL")
    estado = Column(
        String(20), nullable=False, default="pending", server_default="pending", index=True
    )
    idempotency_key = Column(String(255), nullable=False, unique=True)
    provider_order_id = Column(String(255), nullable=True, unique=True)
    checkout_url = Column(String(2000), nullable=True)
    payment_id = Column(String(255), nullable=True, unique=True)
    billing_period = Column(String(20), nullable=True)
    usage_unit = Column(String(50), nullable=True)
    usage_limit = Column(Integer, nullable=True)
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.now())
    atualizado_em = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=func.now(),
    )

    offer = relationship("CheckoutOffer")
    capabilities = relationship(
        "OrdemCheckoutCapability",
        back_populates="ordem",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="OrdemCheckoutCapability.codigo",
    )


class OrdemCheckoutCapability(Base):
    __tablename__ = "ordem_checkout_capabilities"
    __table_args__ = (
        UniqueConstraint(
            "ordem_id", "codigo", name="uq_ordem_checkout_capabilities_ordem_codigo"
        ),
        CheckConstraint(
            "codigo = lower(codigo) AND codigo = trim(codigo) AND length(codigo) > 0",
            name="ck_ordem_checkout_capabilities_codigo_canonico",
        ),
    )

    id = Column(Integer, primary_key=True)
    ordem_id = Column(
        Integer,
        ForeignKey("ordens_checkout.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    codigo = Column(String(120), nullable=False)

    ordem = relationship("OrdemCheckout", back_populates="capabilities")


class EventoPagamento(Base):
    __tablename__ = "eventos_pagamento"

    id = Column(Integer, primary_key=True)
    ordem_id = Column(Integer, ForeignKey("ordens_checkout.id"), nullable=False, index=True)
    notification_id = Column(String(255), nullable=False, unique=True)
    payment_id = Column(String(255), nullable=False, index=True)
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.now())


class Entitlement(Base):
    __tablename__ = "entitlements"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('active', 'under_review', 'suspended')",
            name="ck_entitlements_estado_valido",
        ),
    )

    id = Column(Integer, primary_key=True)
    ordem_id = Column(
        Integer, ForeignKey("ordens_checkout.id"), nullable=False, unique=True
    )
    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    plano_id = Column(Integer, ForeignKey("planos.id"), nullable=False, index=True)
    estado = Column(
        String(20), nullable=False, default="active", server_default="active", index=True
    )
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.now())


class CheckoutOffer(Base):
    __tablename__ = "checkout_offers"
    __table_args__ = (
        UniqueConstraint("codigo", name="uq_checkout_offers_codigo"),
        CheckConstraint("vertical IN ('tax', 'document')", name="ck_checkout_offers_vertical"),
        CheckConstraint(
            "commercial_model IN ('monthly', 'one_time', 'negotiated')",
            name="ck_checkout_offers_commercial_model",
        ),
        CheckConstraint(
            "subject_type IN ('cpf', 'company', 'institution')",
            name="ck_checkout_offers_subject_type",
        ),
        CheckConstraint(
            "estado IN ('draft', 'published', 'retired')",
            name="ck_checkout_offers_estado",
        ),
        CheckConstraint("contract_version > 0", name="ck_checkout_offers_contract_version"),
        CheckConstraint(
            "codigo = lower(codigo) AND codigo = trim(codigo) "
            "AND length(codigo) > 0 AND codigo NOT LIKE '%--%'",
            name="ck_checkout_offers_codigo_canonico",
        ),
        CheckConstraint(
            "(commercial_model = 'monthly' AND moeda = 'BRL' AND preco > 0 "
            "AND billing_period = 'month' AND usage_unit IS NULL AND usage_limit IS NULL) "
            "OR (commercial_model = 'one_time' AND moeda = 'BRL' AND preco > 0 "
            "AND billing_period IS NULL AND usage_unit IS NOT NULL "
            "AND length(trim(usage_unit)) > 0 AND usage_limit > 0) "
            "OR (commercial_model = 'negotiated' AND moeda IS NULL AND preco IS NULL "
            "AND billing_period IS NULL AND usage_unit IS NULL AND usage_limit IS NULL)",
            name="ck_checkout_offers_commercial_configuration",
        ),
    )

    id = Column(Integer, primary_key=True)
    codigo = Column(String(120), nullable=False, index=True)
    nome_publico = Column(String(255), nullable=False)
    vertical = Column(String(20), nullable=False)
    commercial_model = Column(String(20), nullable=False)
    subject_type = Column(String(20), nullable=False)
    estado = Column(String(20), nullable=False, default="draft", server_default="draft")
    moeda = Column(String(3), nullable=True)
    preco = Column(Numeric(12, 2), nullable=True)
    billing_period = Column(String(20), nullable=True)
    usage_unit = Column(String(50), nullable=True)
    usage_limit = Column(Integer, nullable=True)
    contract_version = Column(Integer, nullable=False)
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.now())
    atualizado_em = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=func.now(),
    )

    capabilities = relationship(
        "CheckoutOfferCapability",
        back_populates="offer",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CheckoutOfferCapability(Base):
    __tablename__ = "checkout_offer_capabilities"
    __table_args__ = (
        UniqueConstraint("offer_id", "codigo", name="uq_checkout_offer_capabilities_offer_codigo"),
        CheckConstraint(
            "codigo = lower(codigo) AND codigo = trim(codigo) AND length(codigo) > 0",
            name="ck_checkout_offer_capabilities_codigo_canonico",
        ),
    )

    id = Column(Integer, primary_key=True)
    offer_id = Column(
        Integer,
        ForeignKey("checkout_offers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    codigo = Column(String(120), nullable=False)

    offer = relationship("CheckoutOffer", back_populates="capabilities")


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
    __table_args__ = (
        UniqueConstraint(
            "effect_idempotency_key",
            name="uq_alertas_fiscais_effect_idempotency_key",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    effect_idempotency_key = Column(String(64), nullable=True)
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

_EXTRACTION_EVENT_STATE = {
    "criacao": "pendente",
    "inicio": "em_processamento",
    "conclusao": "concluida",
    "falha": "falhada",
    "cancelamento": "cancelada",
}

_EXTRACTION_TERMINAL_STATES = {
    "concluida",
    "falhada",
    "cancelada",
}

_EXTRACTION_OUTCOMES = (
    "conclusivo",
    "inconclusivo",
    "rejeitado",
)

_RULE_REVIEW_EVENT_OUTCOMES = {
    "extracao_registada": {"pendente"},
    "quarentena_registada": {"pendente", "bloqueada"},
    "validacao_iniciada": {"pendente"},
    "revisao_reservada_iniciada": {"pendente"},
    "revisao_concluida": {"validada", "rejeitada", "bloqueada"},
    "retirada_registada": {"retirada"},
}

_RULE_REVIEW_EVENTS = tuple(_RULE_REVIEW_EVENT_OUTCOMES)
_RULE_REVIEW_OUTCOMES = (
    "pendente",
    "validada",
    "rejeitada",
    "bloqueada",
    "retirada",
)

_NORMATIVE_RELATION_TYPES = (
    "rectifica",
    "republica",
    "altera",
    "substitui",
    "revoga",
    "complementa",
    "referencia",
    "sucede",
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


class ExtractionRun(Base):
    """One immutable event in one exact technical extraction attempt."""

    __tablename__ = "extraction_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["normative_artifact_id", "artifact_hash"],
            [
                "normative_artifacts.normative_artifact_id",
                "normative_artifacts.artifact_hash",
            ],
            name="fk_extraction_runs_exact_artifact",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "extraction_run_id",
            "event_sequence",
            name="uq_extraction_runs_identity_sequence",
        ),
        UniqueConstraint(
            "normative_artifact_id",
            "artifact_hash",
            "extractor_id",
            "extractor_version",
            "parameters_hash",
            "attempt_number",
            "event_sequence",
            name="uq_extraction_runs_exact_attempt_sequence",
        ),
        UniqueConstraint(
            "extraction_run_record_id",
            "extraction_run_id",
            "normative_artifact_id",
            "artifact_hash",
            "attempt_number",
            name="uq_extraction_runs_record_attempt",
        ),
        UniqueConstraint(
            "extraction_run_record_id",
            "extraction_run_id",
            "normative_artifact_id",
            "artifact_hash",
            "extractor_id",
            "extractor_version",
            "parameters_hash",
            "attempt_number",
            "run_event",
            "projected_state",
            name="uq_extraction_runs_exact_projection",
        ),
        ForeignKeyConstraint(
            [
                "previous_extraction_run_record_id",
                "extraction_run_id",
                "normative_artifact_id",
                "artifact_hash",
                "attempt_number",
            ],
            [
                "extraction_runs.extraction_run_record_id",
                "extraction_runs.extraction_run_id",
                "extraction_runs.normative_artifact_id",
                "extraction_runs.artifact_hash",
                "extraction_runs.attempt_number",
            ],
            name="fk_extraction_runs_previous_same_attempt",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "authenticity_verification_record_id",
                "normative_artifact_id",
                "artifact_hash",
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
            name="fk_extraction_runs_authenticity_favorable",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "integrity_verification_record_id",
                "normative_artifact_id",
                "artifact_hash",
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
            name="fk_extraction_runs_integrity_favorable",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "preservation_verification_record_id",
                "normative_artifact_id",
                "artifact_hash",
                "preservation_predecessor_type",
                "preservation_predecessor_outcome",
            ],
            [
                "artifact_verification_records.artifact_verification_record_id",
                "artifact_verification_records.normative_artifact_id",
                "artifact_verification_records.verified_artifact_hash",
                "artifact_verification_records.verification_type",
                "artifact_verification_records.outcome",
            ],
            name="fk_extraction_runs_preservation_favorable",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "record_hash",
            name="uq_extraction_runs_record_hash",
        ),
        CheckConstraint(
            "run_event IN "
            "('criacao', 'inicio', 'conclusao', 'falha', 'cancelamento')",
            name="ck_extraction_runs_event_valid",
        ),
        CheckConstraint(
            "projected_state IN "
            "('pendente', 'em_processamento', 'concluida', "
            "'falhada', 'cancelada')",
            name="ck_extraction_runs_state_valid",
        ),
        CheckConstraint(
            "(run_event = 'criacao' AND projected_state = 'pendente') "
            "OR (run_event = 'inicio' "
            "AND projected_state = 'em_processamento') "
            "OR (run_event = 'conclusao' "
            "AND projected_state = 'concluida') "
            "OR (run_event = 'falha' AND projected_state = 'falhada') "
            "OR (run_event = 'cancelamento' "
            "AND projected_state = 'cancelada')",
            name="ck_extraction_runs_event_state_pair",
        ),
        CheckConstraint(
            "attempt_number > 0",
            name="ck_extraction_runs_attempt_positive",
        ),
        CheckConstraint(
            "event_sequence > 0",
            name="ck_extraction_runs_sequence_positive",
        ),
        CheckConstraint(
            "(event_sequence = 1 "
            "AND run_event = 'criacao' "
            "AND projected_state = 'pendente' "
            "AND previous_extraction_run_record_id IS NULL) "
            "OR (event_sequence > 1 "
            "AND previous_extraction_run_record_id IS NOT NULL)",
            name="ck_extraction_runs_initial_or_predecessor",
        ),
        CheckConstraint(
            "previous_extraction_run_record_id IS NULL "
            "OR previous_extraction_run_record_id "
            "<> extraction_run_record_id",
            name="ck_extraction_runs_no_self_reference",
        ),
        CheckConstraint(
            "("
            "authenticity_verification_record_id IS NULL "
            "AND authenticity_predecessor_type IS NULL "
            "AND authenticity_predecessor_outcome IS NULL "
            "AND integrity_verification_record_id IS NULL "
            "AND integrity_predecessor_type IS NULL "
            "AND integrity_predecessor_outcome IS NULL "
            "AND preservation_verification_record_id IS NULL "
            "AND preservation_predecessor_type IS NULL "
            "AND preservation_predecessor_outcome IS NULL"
            ") OR ("
            "authenticity_verification_record_id IS NOT NULL "
            "AND authenticity_predecessor_type = 'authenticity' "
            "AND authenticity_predecessor_outcome "
            "= 'conclusivo_favoravel' "
            "AND integrity_verification_record_id IS NOT NULL "
            "AND integrity_predecessor_type = 'integrity' "
            "AND integrity_predecessor_outcome "
            "= 'conclusivo_favoravel' "
            "AND preservation_verification_record_id IS NOT NULL "
            "AND preservation_predecessor_type = 'preservation' "
            "AND preservation_predecessor_outcome "
            "= 'conclusivo_favoravel'"
            ")",
            name="ck_extraction_runs_favorable_verification_gates",
        ),
        CheckConstraint(
            "length(trim(extractor_id)) > 0",
            name="ck_extraction_runs_extractor_not_empty",
        ),
        CheckConstraint(
            "length(trim(extractor_version)) > 0",
            name="ck_extraction_runs_version_not_empty",
        ),
        CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL "
            "OR finished_at >= started_at",
            name="ck_extraction_runs_time_order",
        ),
        CheckConstraint(
            "length(artifact_hash) = 64",
            name="ck_extraction_runs_artifact_hash_len",
        ),
        CheckConstraint(
            "length(parameters_hash) = 64",
            name="ck_extraction_runs_parameters_hash_len",
        ),
        CheckConstraint(
            "length(record_hash) = 64",
            name="ck_extraction_runs_record_hash_len",
        ),
    )

    extraction_run_record_id = Column(String(64), primary_key=True)
    extraction_run_id = Column(String(64), nullable=False, index=True)
    normative_artifact_id = Column(String(64), nullable=False, index=True)
    artifact_hash = Column(String(64), nullable=False, index=True)
    extractor_id = Column(String(255), nullable=False, index=True)
    extractor_version = Column(String(128), nullable=False)
    parameters_hash = Column(String(64), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)
    run_event = Column(String(32), nullable=False, index=True)
    projected_state = Column(String(32), nullable=False, index=True)
    event_sequence = Column(Integer, nullable=False)
    previous_extraction_run_record_id = Column(String(64), nullable=True)

    authenticity_verification_record_id = Column(String(64), nullable=True)
    authenticity_predecessor_type = Column(String(32), nullable=True)
    authenticity_predecessor_outcome = Column(String(32), nullable=True)

    integrity_verification_record_id = Column(String(64), nullable=True)
    integrity_predecessor_type = Column(String(32), nullable=True)
    integrity_predecessor_outcome = Column(String(32), nullable=True)

    preservation_verification_record_id = Column(String(64), nullable=True)
    preservation_predecessor_type = Column(String(32), nullable=True)
    preservation_predecessor_outcome = Column(String(32), nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    occurred_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    structured_error = Column(JSON, nullable=True)
    evidence = Column(JSON, nullable=False)
    provenance = Column(JSON, nullable=False)
    record_hash = Column(String(64), nullable=False)


class ExtractionResult(Base):
    """Immutable structured result produced by one concluded extraction run."""

    __tablename__ = "extraction_results"
    __table_args__ = (
        ForeignKeyConstraint(
            [
                "extraction_run_record_id",
                "extraction_run_id",
                "normative_artifact_id",
                "artifact_hash",
                "extractor_id",
                "extractor_version",
                "parameters_hash",
                "attempt_number",
                "run_event",
                "run_state",
            ],
            [
                "extraction_runs.extraction_run_record_id",
                "extraction_runs.extraction_run_id",
                "extraction_runs.normative_artifact_id",
                "extraction_runs.artifact_hash",
                "extraction_runs.extractor_id",
                "extraction_runs.extractor_version",
                "extraction_runs.parameters_hash",
                "extraction_runs.attempt_number",
                "extraction_runs.run_event",
                "extraction_runs.projected_state",
            ],
            name="fk_extraction_results_concluded_run",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "extraction_result_id",
            "record_hash",
            name="uq_extraction_results_identity_hash",
        ),
        UniqueConstraint(
            "extraction_run_record_id",
            name="uq_extraction_results_single_per_run_completion",
        ),
        UniqueConstraint(
            "record_hash",
            name="uq_extraction_results_record_hash",
        ),
        CheckConstraint(
            "run_event = 'conclusao' AND run_state = 'concluida'",
            name="ck_extraction_results_concluded_run",
        ),
        CheckConstraint(
            "outcome IN ('conclusivo', 'inconclusivo', 'rejeitado')",
            name="ck_extraction_results_outcome_valid",
        ),
        CheckConstraint(
            "attempt_number > 0",
            name="ck_extraction_results_attempt_positive",
        ),
        CheckConstraint(
            "length(trim(extractor_id)) > 0",
            name="ck_extraction_results_extractor_not_empty",
        ),
        CheckConstraint(
            "length(trim(extractor_version)) > 0",
            name="ck_extraction_results_version_not_empty",
        ),
        CheckConstraint(
            "length(artifact_hash) = 64",
            name="ck_extraction_results_artifact_hash_len",
        ),
        CheckConstraint(
            "length(parameters_hash) = 64",
            name="ck_extraction_results_parameters_hash_len",
        ),
        CheckConstraint(
            "length(record_hash) = 64",
            name="ck_extraction_results_record_hash_len",
        ),
    )

    extraction_result_id = Column(String(64), primary_key=True)
    extraction_run_record_id = Column(String(64), nullable=False)
    extraction_run_id = Column(String(64), nullable=False, index=True)
    normative_artifact_id = Column(String(64), nullable=False, index=True)
    artifact_hash = Column(String(64), nullable=False, index=True)
    extractor_id = Column(String(255), nullable=False, index=True)
    extractor_version = Column(String(128), nullable=False)
    parameters_hash = Column(String(64), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)
    run_event = Column(
        String(32),
        nullable=False,
        default="conclusao",
        server_default="conclusao",
    )
    run_state = Column(
        String(32),
        nullable=False,
        default="concluida",
        server_default="concluida",
    )
    outcome = Column(String(32), nullable=False, index=True)
    structured_content = Column(JSON, nullable=False)
    evidence = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    record_hash = Column(String(64), nullable=False)

class RuleVersion(Base):
    """Immutable structured normative rule produced from an exact result."""

    __tablename__ = "rule_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            [
                "extraction_result_id",
                "extraction_result_record_hash",
            ],
            [
                "extraction_results.extraction_result_id",
                "extraction_results.record_hash",
            ],
            name="fk_rule_versions_exact_extraction_result",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "rule_id",
            "rule_version",
            name="uq_rule_versions_identity",
        ),
        UniqueConstraint(
            "rule_id",
            "rule_version",
            "rule_hash",
            name="uq_rule_versions_exact_subject",
        ),
        UniqueConstraint(
            "rule_hash",
            name="uq_rule_versions_rule_hash",
        ),
        UniqueConstraint(
            "record_hash",
            name="uq_rule_versions_record_hash",
        ),
        CheckConstraint(
            "rule_version > 0",
            name="ck_rule_versions_version_positive",
        ),
        CheckConstraint(
            "length(rule_hash) = 64",
            name="ck_rule_versions_rule_hash_len",
        ),
        CheckConstraint(
            "length(extraction_result_record_hash) = 64",
            name="ck_rule_versions_result_hash_len",
        ),
        CheckConstraint(
            "length(record_hash) = 64",
            name="ck_rule_versions_record_hash_len",
        ),
    )

    rule_version_record_id = Column(String(64), primary_key=True)
    rule_id = Column(String(64), nullable=False, index=True)
    rule_version = Column(Integer, nullable=False)
    rule_hash = Column(String(64), nullable=False, index=True)
    extraction_result_id = Column(String(64), nullable=False, index=True)
    extraction_result_record_hash = Column(String(64), nullable=False)
    structured_content = Column(JSON, nullable=False)
    declared_material_validity = Column(JSON, nullable=False)
    normative_references = Column(JSON, nullable=False)
    exact_precedence_policy_reference = Column(JSON, nullable=False)
    evidence = Column(JSON, nullable=False)
    provenance = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    record_hash = Column(String(64), nullable=False)


class RuleReviewRecord(Base):
    """Immutable review event for one exact RuleVersion."""

    __tablename__ = "rule_review_records"
    __table_args__ = (
        ForeignKeyConstraint(
            [
                "subject_id",
                "subject_version",
                "subject_hash",
            ],
            [
                "rule_versions.rule_id",
                "rule_versions.rule_version",
                "rule_versions.rule_hash",
            ],
            name="fk_rule_review_records_exact_rule_version",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "record_hash",
            name="uq_rule_review_records_record_hash",
        ),
        CheckConstraint(
            "subject_version > 0",
            name="ck_rule_review_records_subject_version_positive",
        ),
        CheckConstraint(
            """
            review_event IN (
                'extracao_registada',
                'quarentena_registada',
                'validacao_iniciada',
                'revisao_reservada_iniciada',
                'revisao_concluida',
                'retirada_registada'
            )
            """,
            name="ck_rule_review_records_event_valid",
        ),
        CheckConstraint(
            """
            outcome IN (
                'pendente',
                'validada',
                'rejeitada',
                'bloqueada',
                'retirada'
            )
            """,
            name="ck_rule_review_records_outcome_valid",
        ),
        CheckConstraint(
            """
            (
                review_event = 'extracao_registada'
                AND outcome = 'pendente'
            )
            OR (
                review_event = 'quarentena_registada'
                AND outcome IN ('pendente', 'bloqueada')
            )
            OR (
                review_event = 'validacao_iniciada'
                AND outcome = 'pendente'
            )
            OR (
                review_event = 'revisao_reservada_iniciada'
                AND outcome = 'pendente'
            )
            OR (
                review_event = 'revisao_concluida'
                AND outcome IN ('validada', 'rejeitada', 'bloqueada')
            )
            OR (
                review_event = 'retirada_registada'
                AND outcome = 'retirada'
            )
            """,
            name="ck_rule_review_records_event_outcome_pair",
        ),
        CheckConstraint(
            "length(trim(reviewer)) > 0",
            name="ck_rule_review_records_reviewer_not_empty",
        ),
        CheckConstraint(
            "length(subject_hash) = 64",
            name="ck_rule_review_records_subject_hash_len",
        ),
        CheckConstraint(
            "length(record_hash) = 64",
            name="ck_rule_review_records_record_hash_len",
        ),
    )

    rule_review_record_id = Column(String(64), primary_key=True)
    subject_id = Column(String(64), nullable=False, index=True)
    subject_version = Column(Integer, nullable=False)
    subject_hash = Column(String(64), nullable=False, index=True)
    reviewer = Column(String(255), nullable=False)
    review_event = Column(String(64), nullable=False, index=True)
    outcome = Column(String(32), nullable=False, index=True)
    evidence = Column(JSON, nullable=False)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    record_hash = Column(String(64), nullable=False)



class NormativeRelationVersion(Base):
    """Immutable content of one exact normative relation."""

    __tablename__ = "normative_relation_versions"
    __table_args__ = (
        UniqueConstraint(
            "normative_relation_id",
            "normative_relation_version",
            name="uq_normative_relation_versions_identity",
        ),
        UniqueConstraint(
            "normative_relation_id",
            "normative_relation_version",
            "normative_relation_hash",
            name="uq_normative_relation_versions_exact_subject",
        ),
        UniqueConstraint(
            "normative_relation_hash",
            name="uq_normative_relation_versions_relation_hash",
        ),
        UniqueConstraint(
            "record_hash",
            name="uq_normative_relation_versions_record_hash",
        ),
        CheckConstraint(
            "normative_relation_version > 0",
            name=(
                "ck_normative_relation_versions_"
                "version_positive"
            ),
        ),
        CheckConstraint(
            "source_subject_version > 0",
            name=(
                "ck_normative_relation_versions_"
                "source_version_positive"
            ),
        ),
        CheckConstraint(
            "target_subject_version > 0",
            name=(
                "ck_normative_relation_versions_"
                "target_version_positive"
            ),
        ),
        CheckConstraint(
            "normative_relation_hash "
            "GLOB '[0-9a-f]*' "
            "AND length(normative_relation_hash) = 64",
            name=(
                "ck_normative_relation_versions_"
                "relation_hash_sha256"
            ),
        ),
        CheckConstraint(
            "source_subject_hash "
            "GLOB '[0-9a-f]*' "
            "AND length(source_subject_hash) = 64",
            name=(
                "ck_normative_relation_versions_"
                "source_hash_sha256"
            ),
        ),
        CheckConstraint(
            "target_subject_hash "
            "GLOB '[0-9a-f]*' "
            "AND length(target_subject_hash) = 64",
            name=(
                "ck_normative_relation_versions_"
                "target_hash_sha256"
            ),
        ),
        CheckConstraint(
            "record_hash "
            "GLOB '[0-9a-f]*' "
            "AND length(record_hash) = 64",
            name=(
                "ck_normative_relation_versions_"
                "record_hash_sha256"
            ),
        ),
        CheckConstraint(
            """
            relation_type IN (
                'rectifica',
                'republica',
                'altera',
                'substitui',
                'revoga',
                'complementa',
                'referencia',
                'sucede'
            )
            """,
            name=(
                "ck_normative_relation_versions_"
                "relation_type_valid"
            ),
        ),
    )

    normative_relation_version_record_id = Column(
        String(64),
        primary_key=True,
    )
    normative_relation_id = Column(
        String(64),
        nullable=False,
        index=True,
    )
    normative_relation_version = Column(
        Integer,
        nullable=False,
    )
    normative_relation_hash = Column(
        String(64),
        nullable=False,
        index=True,
    )

    source_subject_type = Column(
        String(64),
        nullable=False,
    )
    source_subject_id = Column(
        String(64),
        nullable=False,
        index=True,
    )
    source_subject_version = Column(
        Integer,
        nullable=False,
    )
    source_subject_hash = Column(
        String(64),
        nullable=False,
        index=True,
    )

    target_subject_type = Column(
        String(64),
        nullable=False,
    )
    target_subject_id = Column(
        String(64),
        nullable=False,
        index=True,
    )
    target_subject_version = Column(
        Integer,
        nullable=False,
    )
    target_subject_hash = Column(
        String(64),
        nullable=False,
        index=True,
    )

    relation_type = Column(
        String(32),
        nullable=False,
        index=True,
    )
    declared_material_validity = Column(
        JSON,
        nullable=False,
    )
    structured_content = Column(
        JSON,
        nullable=False,
    )
    evidence = Column(
        JSON,
        nullable=False,
    )
    normative_references = Column(
        JSON,
        nullable=False,
    )
    exact_precedence_policy_reference = Column(
        JSON,
        nullable=False,
    )
    provenance = Column(
        JSON,
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    record_hash = Column(
        String(64),
        nullable=False,
    )


class RelationReviewRecord(Base):
    """Immutable review event for one exact relation version."""

    __tablename__ = "relation_review_records"
    __table_args__ = (
        ForeignKeyConstraint(
            [
                "subject_id",
                "subject_version",
                "subject_hash",
            ],
            [
                (
                    "normative_relation_versions."
                    "normative_relation_id"
                ),
                (
                    "normative_relation_versions."
                    "normative_relation_version"
                ),
                (
                    "normative_relation_versions."
                    "normative_relation_hash"
                ),
            ],
            name=(
                "fk_relation_review_records_"
                "exact_relation"
            ),
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "record_hash",
            name=(
                "uq_relation_review_records_"
                "record_hash"
            ),
        ),
        CheckConstraint(
            "subject_version > 0",
            name=(
                "ck_relation_review_records_"
                "subject_version_positive"
            ),
        ),
        CheckConstraint(
            """
            review_event IN (
                'extracao_registada',
                'quarentena_registada',
                'validacao_iniciada',
                'revisao_reservada_iniciada',
                'revisao_concluida',
                'retirada_registada'
            )
            """,
            name=(
                "ck_relation_review_records_"
                "event_valid"
            ),
        ),
        CheckConstraint(
            """
            outcome IN (
                'pendente',
                'validada',
                'rejeitada',
                'bloqueada',
                'retirada'
            )
            """,
            name=(
                "ck_relation_review_records_"
                "outcome_valid"
            ),
        ),
        CheckConstraint(
            """
            (
                review_event = 'extracao_registada'
                AND outcome = 'pendente'
            )
            OR (
                review_event = 'quarentena_registada'
                AND outcome IN ('pendente', 'bloqueada')
            )
            OR (
                review_event = 'validacao_iniciada'
                AND outcome = 'pendente'
            )
            OR (
                review_event =
                    'revisao_reservada_iniciada'
                AND outcome = 'pendente'
            )
            OR (
                review_event = 'revisao_concluida'
                AND outcome IN (
                    'validada',
                    'rejeitada',
                    'bloqueada'
                )
            )
            OR (
                review_event = 'retirada_registada'
                AND outcome = 'retirada'
            )
            """,
            name=(
                "ck_relation_review_records_"
                "event_outcome_pair"
            ),
        ),
    )

    relation_review_record_id = Column(
        String(64),
        primary_key=True,
    )
    subject_id = Column(
        String(64),
        nullable=False,
        index=True,
    )
    subject_version = Column(
        Integer,
        nullable=False,
    )
    subject_hash = Column(
        String(64),
        nullable=False,
        index=True,
    )
    reviewer = Column(
        String(255),
        nullable=False,
    )
    review_event = Column(
        String(64),
        nullable=False,
        index=True,
    )
    outcome = Column(
        String(32),
        nullable=False,
        index=True,
    )
    evidence = Column(
        JSON,
        nullable=False,
    )
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    record_hash = Column(
        String(64),
        nullable=False,
    )


class PolicyVersion(Base):
    """Immutable content of one exact institutional policy version."""

    __tablename__ = "policy_versions"
    __table_args__ = (
        UniqueConstraint("policy_id", "policy_version", name="uq_policy_versions_identity"),
        UniqueConstraint("policy_id", "policy_version", "policy_hash", name="uq_policy_versions_exact_subject"),
        UniqueConstraint("policy_hash", name="uq_policy_versions_policy_hash"),
        UniqueConstraint("record_hash", name="uq_policy_versions_record_hash"),
        CheckConstraint("policy_version > 0", name="ck_policy_versions_version_positive"),
        CheckConstraint("policy_type IN ('activation_authority', 'automation_envelope', 'normative_precedence', 'normative_continuity', 'coverage_contract')", name="ck_policy_versions_policy_type_valid"),
        CheckConstraint("length(policy_hash) = 64", name="ck_policy_versions_policy_hash_len"),
        CheckConstraint("length(record_hash) = 64", name="ck_policy_versions_record_hash_len"),
    )

    policy_version_record_id = Column(String(64), primary_key=True)
    policy_type = Column(String(32), nullable=False, index=True)
    policy_id = Column(String(64), nullable=False, index=True)
    policy_version = Column(Integer, nullable=False)
    policy_hash = Column(String(64), nullable=False, index=True)
    domain = Column(String(255), nullable=False)
    scope = Column(JSON, nullable=False)
    declared_material_applicability = Column(JSON, nullable=False)
    modalities = Column(JSON, nullable=False)
    permitted_authorization_classes = Column(JSON, nullable=False)
    permitted_execution_modes = Column(JSON, nullable=False)
    gates = Column(JSON, nullable=False)
    roles = Column(JSON, nullable=False)
    segregation_of_duties = Column(JSON, nullable=False)
    limits = Column(JSON, nullable=False)
    rules = Column(JSON, nullable=False)
    exact_references = Column(JSON, nullable=False)
    origin_evidence = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    record_hash = Column(String(64), nullable=False)


class PolicyDecision(Base):
    """Immutable institutional event over one exact PolicyVersion."""

    __tablename__ = "policy_decisions"
    __table_args__ = (
        ForeignKeyConstraint(["policy_id", "policy_version", "policy_hash"], ["policy_versions.policy_id", "policy_versions.policy_version", "policy_versions.policy_hash"], name="fk_policy_decisions_exact_policy_version", ondelete="RESTRICT"),
        ForeignKeyConstraint(["previous_decision_id"], ["policy_decisions.decision_id"], name="fk_policy_decisions_previous_decision", ondelete="RESTRICT"),
        UniqueConstraint("idempotency_key", name="uq_policy_decisions_idempotency_key"),
        UniqueConstraint("record_hash", name="uq_policy_decisions_record_hash"),
        CheckConstraint("policy_version > 0", name="ck_policy_decisions_version_positive"),
        CheckConstraint("policy_type IN ('activation_authority', 'automation_envelope', 'normative_precedence', 'normative_continuity', 'coverage_contract')", name="ck_policy_decisions_policy_type_valid"),
        CheckConstraint("decision_event IN ('submetida', 'auditoria_iniciada', 'auditada_favoravelmente', 'auditada_desfavoravelmente', 'ratificada', 'rejeitada', 'cancelada')", name="ck_policy_decisions_event_valid"),
        CheckConstraint("institutional_role IN ('proponente_institucional', 'auditor_independente', 'autoridade_constitucional_final', 'autoridade_institucional_competente')", name="ck_policy_decisions_role_valid"),
        CheckConstraint("length(policy_hash) = 64", name="ck_policy_decisions_policy_hash_len"),
        CheckConstraint("length(record_hash) = 64", name="ck_policy_decisions_record_hash_len"),
    )

    decision_id = Column(String(64), primary_key=True)
    decision_event = Column(String(32), nullable=False, index=True)
    policy_type = Column(String(32), nullable=False, index=True)
    policy_id = Column(String(64), nullable=False, index=True)
    policy_version = Column(Integer, nullable=False)
    policy_hash = Column(String(64), nullable=False, index=True)
    actor = Column(String(255), nullable=False)
    institutional_role = Column(String(64), nullable=False)
    evidence = Column(JSON, nullable=False)
    rationale = Column(Text, nullable=False)
    previous_decision_id = Column(String(64), nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    idempotency_key = Column(String(255), nullable=False)
    record_hash = Column(String(64), nullable=False)


class BootstrapAuthorityRecord(Base):
    """Manual constitutional authority for the first exact policy chain."""

    __tablename__ = "bootstrap_authority_records"
    __table_args__ = (
        ForeignKeyConstraint(["policy_id", "policy_version", "policy_hash"], ["policy_versions.policy_id", "policy_versions.policy_version", "policy_versions.policy_hash"], name="fk_bootstrap_authority_records_exact_policy_version", ondelete="RESTRICT"),
        UniqueConstraint("record_hash", name="uq_bootstrap_authority_records_record_hash"),
        CheckConstraint("policy_type = 'activation_authority'", name="ck_bootstrap_authority_records_policy_type"),
        CheckConstraint("policy_version > 0", name="ck_bootstrap_authority_records_version_positive"),
        CheckConstraint("independent_audit_result = 'favoravel'", name="ck_bootstrap_authority_records_audit_favorable"),
        CheckConstraint("validity = 'valida'", name="ck_bootstrap_authority_records_validity"),
        CheckConstraint("submission_mode = 'manual' AND audit_mode = 'manual' AND ratification_mode = 'manual' AND activation_mode = 'manual'", name="ck_bootstrap_authority_records_manual_only"),
        CheckConstraint("actor_proponente <> actor_auditor AND actor_proponente <> actor_ratificador AND actor_auditor <> actor_ratificador", name="ck_bootstrap_authority_records_actor_segregation"),
        CheckConstraint("length(policy_hash) = 64", name="ck_bootstrap_authority_records_policy_hash_len"),
        CheckConstraint("length(record_hash) = 64", name="ck_bootstrap_authority_records_record_hash_len"),
    )

    bootstrap_authority_record_id = Column(String(64), primary_key=True)
    policy_type = Column(String(32), nullable=False)
    policy_id = Column(String(64), nullable=False, index=True)
    policy_version = Column(Integer, nullable=False)
    policy_hash = Column(String(64), nullable=False)
    domain = Column(String(255), nullable=False)
    scope = Column(JSON, nullable=False)
    actor_proponente = Column(String(255), nullable=False)
    actor_auditor = Column(String(255), nullable=False)
    independent_audit_result = Column(String(32), nullable=False)
    constitutional_authority_declaration = Column(Text, nullable=False)
    actor_ratificador = Column(String(255), nullable=False)
    segregation_evidence = Column(JSON, nullable=False)
    evidence = Column(JSON, nullable=False)
    validity = Column(String(32), nullable=False)
    submission_mode = Column(String(16), nullable=False)
    audit_mode = Column(String(16), nullable=False)
    ratification_mode = Column(String(16), nullable=False)
    activation_mode = Column(String(16), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    provenance = Column(JSON, nullable=False)
    record_hash = Column(String(64), nullable=False)


class CoverageContract(Base):
    """Immutable definition of expected source coverage; grants no authority."""

    __tablename__ = "coverage_contracts"
    __table_args__ = (
        UniqueConstraint("coverage_contract_id", "contract_version", name="uq_coverage_contracts_identity"),
        UniqueConstraint("coverage_contract_id", "contract_version", "contract_hash", name="uq_coverage_contracts_exact_subject"),
        UniqueConstraint("contract_hash", name="uq_coverage_contracts_contract_hash"),
        UniqueConstraint("record_hash", name="uq_coverage_contracts_record_hash"),
        CheckConstraint("contract_version > 0", name="ck_coverage_contracts_version_positive"),
        CheckConstraint("contract_state IN ('proposta', 'auditada', 'ratificada', 'revogada')", name="ck_coverage_contracts_state_valid"),
        CheckConstraint("length(contract_hash) = 64", name="ck_coverage_contracts_contract_hash_len"),
        CheckConstraint("length(record_hash) = 64", name="ck_coverage_contracts_record_hash_len"),
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="ck_coverage_contracts_validity_order"),
    )

    coverage_contract_record_id = Column(String(64), primary_key=True)
    coverage_contract_id = Column(String(64), nullable=False, index=True)
    source_id = Column(String(64), nullable=False, index=True)
    contract_version = Column(Integer, nullable=False)
    contract_hash = Column(String(64), nullable=False, index=True)
    contract_state = Column(String(16), nullable=False)
    effective_from = Column(DateTime(timezone=True), nullable=False)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    timezone = Column(String(64), nullable=False)
    expected_calendar = Column(JSON, nullable=False)
    publication_schedule = Column(JSON, nullable=False)
    delay_windows = Column(JSON, nullable=False)
    mandatory_sections = Column(JSON, nullable=False)
    expected_files_partitions = Column(JSON, nullable=False)
    pagination = Column(JSON, nullable=False)
    cursors = Column(JSON, nullable=False)
    empty_response_semantics = Column(JSON, nullable=False)
    proven_absence_rules = Column(JSON, nullable=False)
    authorized_redirects = Column(JSON, nullable=False)
    media_types = Column(JSON, nullable=False)
    adapter_id = Column(String(64), nullable=False)
    compatible_adapter_versions = Column(JSON, nullable=False)
    technical_limits = Column(JSON, nullable=False)
    retry_policy = Column(JSON, nullable=False)
    continuity_policy_reference = Column(JSON, nullable=False)
    evidence = Column(JSON, nullable=False)
    audit = Column(JSON, nullable=False)
    ratification = Column(JSON, nullable=False)
    revocation = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    record_hash = Column(String(64), nullable=False)


class CoverageLedgerEntry(Base):
    """One immutable observation/processing result for one expected unit."""

    __tablename__ = "coverage_ledger_entries"
    __table_args__ = (
        ForeignKeyConstraint(["coverage_contract_id", "contract_version", "contract_hash"], ["coverage_contracts.coverage_contract_id", "coverage_contracts.contract_version", "coverage_contracts.contract_hash"], name="fk_coverage_ledger_entries_exact_contract", ondelete="RESTRICT"),
        UniqueConstraint("coverage_contract_id", "contract_version", "contract_hash", "window_start", "window_end", "unit_order", name="uq_coverage_ledger_entries_unit_order"),
        UniqueConstraint("coverage_ledger_entry_id", "coverage_contract_id", "contract_version", "contract_hash", "window_start", "window_end", name="uq_coverage_ledger_entries_exact_checkpoint_target"),
        UniqueConstraint("record_hash", name="uq_coverage_ledger_entries_record_hash"),
        CheckConstraint("contract_version > 0 AND unit_order > 0 AND fencing_token > 0", name="ck_coverage_ledger_entries_positive_order_fence"),
        CheckConstraint("window_end > window_start", name="ck_coverage_ledger_entries_window_order"),
        CheckConstraint("unit_type IN ('publication', 'section', 'page', 'file', 'partition', 'period')", name="ck_coverage_ledger_entries_unit_type_valid"),
        CheckConstraint("observation_outcome IN ('observed', 'not_observed', 'source_unavailable')", name="ck_coverage_ledger_entries_observation_valid"),
        CheckConstraint("processing_outcome IN ('pending', 'succeeded', 'failed', 'proven_absence')", name="ck_coverage_ledger_entries_processing_valid"),
        CheckConstraint("coverage_outcome IN ('covered', 'gap', 'not_covered')", name="ck_coverage_ledger_entries_coverage_valid"),
        CheckConstraint("response_kind IN ('non_empty', 'empty', 'not_applicable')", name="ck_coverage_ledger_entries_response_kind_valid"),
        CheckConstraint("coverage_outcome <> 'covered' OR processing_outcome IN ('succeeded', 'proven_absence')", name="ck_coverage_ledger_entries_failure_not_covered"),
        CheckConstraint("response_kind <> 'empty' OR coverage_outcome <> 'covered' OR cycle_fully_evaluated", name="ck_coverage_ledger_entries_empty_requires_full_cycle"),
        CheckConstraint("length(contract_hash) = 64 AND length(record_hash) = 64", name="ck_coverage_ledger_entries_hashes_len"),
    )

    coverage_ledger_entry_id = Column(String(64), primary_key=True)
    coverage_contract_id = Column(String(64), nullable=False)
    contract_version = Column(Integer, nullable=False)
    contract_hash = Column(String(64), nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    unit_type = Column(String(16), nullable=False)
    unit_id = Column(String(255), nullable=False)
    unit_order = Column(Integer, nullable=False)
    observation_outcome = Column(String(32), nullable=False)
    processing_outcome = Column(String(32), nullable=False)
    coverage_outcome = Column(String(16), nullable=False)
    response_kind = Column(String(16), nullable=False)
    cycle_fully_evaluated = Column(Boolean, nullable=False, default=False)
    fencing_token = Column(Integer, nullable=False)
    evidence = Column(JSON, nullable=False)
    provenance = Column(JSON, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    record_hash = Column(String(64), nullable=False)


class CoverageCheckpointRecord(Base):
    """Immutable snapshot of independent contiguous coverage frontiers."""

    __tablename__ = "coverage_checkpoint_records"
    __table_args__ = (
        ForeignKeyConstraint(["coverage_contract_id", "contract_version", "contract_hash"], ["coverage_contracts.coverage_contract_id", "coverage_contracts.contract_version", "coverage_contracts.contract_hash"], name="fk_coverage_checkpoint_records_exact_contract", ondelete="RESTRICT"),
        ForeignKeyConstraint(["last_ledger_entry_id", "coverage_contract_id", "contract_version", "contract_hash", "window_start", "window_end"], ["coverage_ledger_entries.coverage_ledger_entry_id", "coverage_ledger_entries.coverage_contract_id", "coverage_ledger_entries.contract_version", "coverage_ledger_entries.contract_hash", "coverage_ledger_entries.window_start", "coverage_ledger_entries.window_end"], name="fk_coverage_checkpoint_records_exact_last_entry", ondelete="RESTRICT"),
        UniqueConstraint("coverage_contract_id", "contract_version", "contract_hash", "window_start", "window_end", "checkpoint_sequence", name="uq_coverage_checkpoint_records_sequence"),
        UniqueConstraint("record_hash", name="uq_coverage_checkpoint_records_record_hash"),
        CheckConstraint("contract_version > 0 AND checkpoint_sequence > 0 AND fencing_token > 0", name="ck_coverage_checkpoint_records_positive_sequence_fence"),
        CheckConstraint("window_end > window_start", name="ck_coverage_checkpoint_records_window_order"),
        CheckConstraint("observed_through IS NULL OR observed_through > 0", name="ck_coverage_checkpoint_records_observed_positive"),
        CheckConstraint("completed_through IS NULL OR completed_through > 0", name="ck_coverage_checkpoint_records_completed_positive"),
        CheckConstraint("covered_through IS NULL OR covered_through > 0", name="ck_coverage_checkpoint_records_covered_positive"),
        CheckConstraint("pending_gap_from IS NULL OR pending_gap_from > 0", name="ck_coverage_checkpoint_records_gap_positive"),
        CheckConstraint("completed_through IS NULL OR observed_through IS NOT NULL AND completed_through <= observed_through", name="ck_coverage_checkpoint_records_completed_within_observed"),
        CheckConstraint("covered_through IS NULL OR completed_through IS NOT NULL AND covered_through <= completed_through", name="ck_coverage_checkpoint_records_covered_within_completed"),
        CheckConstraint("pending_gap_from IS NULL OR pending_gap_from = COALESCE(covered_through, 0) + 1", name="ck_coverage_checkpoint_records_first_gap"),
        CheckConstraint("pending_gap_from IS NOT NULL OR cycle_fully_evaluated", name="ck_coverage_checkpoint_records_no_gap_requires_full_cycle"),
        CheckConstraint("length(contract_hash) = 64 AND length(record_hash) = 64", name="ck_coverage_checkpoint_records_hashes_len"),
    )

    coverage_checkpoint_record_id = Column(String(64), primary_key=True)
    coverage_contract_id = Column(String(64), nullable=False)
    contract_version = Column(Integer, nullable=False)
    contract_hash = Column(String(64), nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    checkpoint_sequence = Column(Integer, nullable=False)
    observed_through = Column(Integer, nullable=True)
    completed_through = Column(Integer, nullable=True)
    covered_through = Column(Integer, nullable=True)
    pending_gap_from = Column(Integer, nullable=True)
    cycle_fully_evaluated = Column(Boolean, nullable=False, default=False)
    last_ledger_entry_id = Column(String(64), nullable=False)
    fencing_token = Column(Integer, nullable=False)
    evidence = Column(JSON, nullable=False)
    provenance = Column(JSON, nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    record_hash = Column(String(64), nullable=False)


class PolicyActivationExecution(Base):
    """Immutable technical attempt to activate one exact policy version."""

    __tablename__ = "policy_activation_executions"
    __table_args__ = (
        ForeignKeyConstraint(["policy_id", "policy_version", "policy_hash"], ["policy_versions.policy_id", "policy_versions.policy_version", "policy_versions.policy_hash"], name="fk_policy_activation_executions_exact_policy", ondelete="RESTRICT"),
        ForeignKeyConstraint(["policy_decision_id"], ["policy_decisions.decision_id"], name="fk_policy_activation_executions_exact_decision", ondelete="RESTRICT"),
        ForeignKeyConstraint(["bootstrap_authority_record_id"], ["bootstrap_authority_records.bootstrap_authority_record_id"], name="fk_policy_activation_executions_exact_bootstrap", ondelete="RESTRICT"),
        ForeignKeyConstraint(["activation_authority_policy_id", "activation_authority_policy_version", "activation_authority_policy_hash"], ["policy_versions.policy_id", "policy_versions.policy_version", "policy_versions.policy_hash"], name="fk_policy_activation_executions_exact_authority_policy", ondelete="RESTRICT"),
        ForeignKeyConstraint(["activation_authority_policy_activation_id"], ["policy_activations.policy_activation_id"], name="fk_policy_activation_executions_exact_authority_activation", ondelete="RESTRICT", use_alter=True),
        ForeignKeyConstraint(["automation_envelope_id", "automation_envelope_version", "automation_envelope_hash"], ["policy_versions.policy_id", "policy_versions.policy_version", "policy_versions.policy_hash"], name="fk_policy_activation_executions_exact_envelope", ondelete="RESTRICT"),
        ForeignKeyConstraint(["automation_envelope_activation_id"], ["policy_activations.policy_activation_id"], name="fk_policy_activation_executions_exact_envelope_activation", ondelete="RESTRICT", use_alter=True),
        UniqueConstraint("idempotency_key", name="uq_policy_activation_executions_idempotency"),
        UniqueConstraint("record_hash", name="uq_policy_activation_executions_record_hash"),
        CheckConstraint("state IN ('pendente','em_execucao','concluida','falhada','cancelada')", name="ck_policy_activation_executions_state"),
        CheckConstraint("authorization_basis_type IN ('bootstrap_authority_record','active_policy_chain')", name="ck_policy_activation_executions_basis"),
        CheckConstraint("authorization_class IN ('constitucional_reservada','humana_delegada','automatica_delegada')", name="ck_policy_activation_executions_class"),
        CheckConstraint("execution_mode IN ('manual','automatico')", name="ck_policy_activation_executions_mode"),
        CheckConstraint("attempt_number > 0 AND fencing_token > 0", name="ck_policy_activation_executions_positive"),
        CheckConstraint("length(policy_hash)=64 AND length(record_hash)=64", name="ck_policy_activation_executions_hashes"),
    )
    policy_activation_execution_id = Column(String(64), primary_key=True)
    policy_decision_id = Column(String(64), nullable=False)
    policy_type = Column(String(32), nullable=False)
    policy_id = Column(String(64), nullable=False)
    policy_version = Column(Integer, nullable=False)
    policy_hash = Column(String(64), nullable=False)
    authorization_basis_type = Column(String(32), nullable=False)
    authorization_class = Column(String(32), nullable=False)
    execution_mode = Column(String(16), nullable=False)
    bootstrap_authority_record_id = Column(String(64), nullable=True)
    bootstrap_authority_record_hash = Column(String(64), nullable=True)
    activation_authority_policy_id = Column(String(64), nullable=True)
    activation_authority_policy_version = Column(Integer, nullable=True)
    activation_authority_policy_hash = Column(String(64), nullable=True)
    activation_authority_policy_activation_id = Column(String(64), nullable=True)
    automation_envelope_id = Column(String(64), nullable=True)
    automation_envelope_version = Column(Integer, nullable=True)
    automation_envelope_hash = Column(String(64), nullable=True)
    automation_envelope_activation_id = Column(String(64), nullable=True)
    attempt_number = Column(Integer, nullable=False)
    actor_or_worker = Column(String(255), nullable=False)
    lease_id = Column(String(64), nullable=False)
    fencing_token = Column(Integer, nullable=False)
    idempotency_key = Column(String(255), nullable=False)
    state = Column(String(16), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    structured_result = Column(JSON, nullable=True)
    structured_error = Column(JSON, nullable=True)
    provenance = Column(JSON, nullable=False)
    record_hash = Column(String(64), nullable=False)


class PolicyActivation(Base):
    __tablename__ = "policy_activations"
    __table_args__ = (
        ForeignKeyConstraint(["policy_activation_execution_id"], ["policy_activation_executions.policy_activation_execution_id"], name="fk_policy_activations_execution", ondelete="RESTRICT"),
        ForeignKeyConstraint(["policy_decision_id"], ["policy_decisions.decision_id"], name="fk_policy_activations_decision", ondelete="RESTRICT"),
        ForeignKeyConstraint(["policy_id", "policy_version", "policy_hash"], ["policy_versions.policy_id", "policy_versions.policy_version", "policy_versions.policy_hash"], name="fk_policy_activations_exact_policy", ondelete="RESTRICT"),
        UniqueConstraint("record_hash", name="uq_policy_activations_record_hash"),
        CheckConstraint("state IN ('activa','suspensa','desactivada','expirada','revogada')", name="ck_policy_activations_state"),
        CheckConstraint("length(policy_hash)=64 AND length(record_hash)=64", name="ck_policy_activations_hashes"),
    )
    policy_activation_id = Column(String(64), primary_key=True)
    policy_activation_execution_id = Column(String(64), nullable=False, unique=True)
    policy_decision_id = Column(String(64), nullable=False)
    policy_type = Column(String(32), nullable=False)
    policy_id = Column(String(64), nullable=False)
    policy_version = Column(Integer, nullable=False)
    policy_hash = Column(String(64), nullable=False)
    domain = Column(String(255), nullable=False)
    modality = Column(String(64), nullable=False)
    operational_interval = Column(JSON, nullable=False)
    activation_generation_id = Column(String(64), nullable=False)
    activated_at = Column(DateTime(timezone=True), nullable=False)
    state = Column(String(16), nullable=False)
    technical_actor = Column(String(255), nullable=False)
    provenance = Column(JSON, nullable=False)
    record_hash = Column(String(64), nullable=False)


class ActivationDecision(Base):
    __tablename__ = "activation_decisions"
    __table_args__ = (
        ForeignKeyConstraint(["previous_activation_decision_id"], ["activation_decisions.activation_decision_id"], name="fk_activation_decisions_previous", ondelete="RESTRICT"),
        UniqueConstraint("idempotency_key", name="uq_activation_decisions_idempotency"), UniqueConstraint("record_hash", name="uq_activation_decisions_record_hash"),
        CheckConstraint("decision_action IN ('activate','suspend','deactivate','expire','revoke')", name="ck_activation_decisions_action"),
        CheckConstraint("decision_outcome IN ('approved','rejected','cancelled')", name="ck_activation_decisions_outcome"),
        CheckConstraint("authorization_class IN ('constitucional_reservada','humana_delegada','automatica_delegada')", name="ck_activation_decisions_class"),
        CheckConstraint("length(scope_hash)=64 AND length(target_manifest_hash)=64 AND length(record_hash)=64", name="ck_activation_decisions_hashes"),
    )
    activation_decision_id = Column(String(64), primary_key=True); decision_action = Column(String(16), nullable=False); decision_outcome = Column(String(16), nullable=False); authorization_class = Column(String(32), nullable=False)
    actor = Column(String(255), nullable=False); institutional_role = Column(String(64), nullable=False); target_scope = Column(JSON, nullable=False); scope_hash = Column(String(64), nullable=False); target_manifest = Column(JSON, nullable=False); target_manifest_hash = Column(String(64), nullable=False)
    authority_bindings = Column(JSON, nullable=False); policy_bindings = Column(JSON, nullable=False); coverage_binding = Column(JSON, nullable=False); continuity_binding = Column(JSON, nullable=False); precedence_binding = Column(JSON, nullable=False); gates_evidence = Column(JSON, nullable=False)
    rationale = Column(Text, nullable=False); evidence = Column(JSON, nullable=False); previous_activation_decision_id = Column(String(64), nullable=True); timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now()); idempotency_key = Column(String(255), nullable=False); record_hash = Column(String(64), nullable=False)


class ActivationExecution(Base):
    __tablename__ = "activation_executions"
    __table_args__ = (
        ForeignKeyConstraint(["activation_decision_id", "activation_decision_record_hash"], ["activation_decisions.activation_decision_id", "activation_decisions.record_hash"], name="fk_activation_executions_exact_decision", ondelete="RESTRICT"),
        UniqueConstraint("idempotency_key", name="uq_activation_executions_idempotency"), UniqueConstraint("record_hash", name="uq_activation_executions_record_hash"), UniqueConstraint("activation_execution_id", "record_hash", name="uq_activation_executions_exact"), UniqueConstraint("activation_execution_id", "activation_decision_id", "activation_decision_record_hash", name="uq_activation_executions_exact_decision_binding"),
        CheckConstraint("state IN ('pending','running','completed','failed','cancelled')", name="ck_activation_executions_state"), CheckConstraint("decision_outcome = 'approved'", name="ck_activation_executions_approved"),
        CheckConstraint("decision_action IN ('activate','suspend','deactivate','expire','revoke')", name="ck_activation_executions_action"), CheckConstraint("authorization_class IN ('constitucional_reservada','humana_delegada','automatica_delegada')", name="ck_activation_executions_class"), CheckConstraint("execution_mode IN ('manual','automatico')", name="ck_activation_executions_mode"), CheckConstraint("authorization_class <> 'constitucional_reservada' OR execution_mode = 'manual'", name="ck_activation_executions_reserved_manual"), CheckConstraint("execution_mode <> 'automatico' OR authorization_class = 'automatica_delegada'", name="ck_activation_executions_automatic_class"), CheckConstraint("attempt_number > 0 AND fencing_token > 0", name="ck_activation_executions_positive"), CheckConstraint("length(activation_decision_record_hash)=64 AND length(scope_hash)=64 AND length(target_manifest_hash)=64 AND length(record_hash)=64", name="ck_activation_executions_hashes"),
    )
    activation_execution_id = Column(String(64), primary_key=True); activation_decision_id = Column(String(64), nullable=False); activation_decision_record_hash = Column(String(64), nullable=False); decision_outcome = Column(String(16), nullable=False); decision_action = Column(String(16), nullable=False); authorization_class = Column(String(32), nullable=False); execution_mode = Column(String(16), nullable=False); state = Column(String(16), nullable=False); scope_hash = Column(String(64), nullable=False); target_manifest_hash = Column(String(64), nullable=False); attempt_number = Column(Integer, nullable=False); actor_or_worker = Column(String(255), nullable=False); lease_id = Column(String(64), nullable=False); fencing_token = Column(Integer, nullable=False); idempotency_key = Column(String(255), nullable=False)
    authority_bindings = Column(JSON, nullable=False); policy_bindings = Column(JSON, nullable=False); coverage_binding = Column(JSON, nullable=False); continuity_binding = Column(JSON, nullable=False); precedence_binding = Column(JSON, nullable=False); gates_evidence = Column(JSON, nullable=False); started_at = Column(DateTime(timezone=True), nullable=True); finished_at = Column(DateTime(timezone=True), nullable=True); structured_result = Column(JSON, nullable=True); structured_error = Column(JSON, nullable=True); provenance = Column(JSON, nullable=False); record_hash = Column(String(64), nullable=False)


class NormativeActivation(Base):
    __tablename__ = "normative_activations"
    __table_args__ = (
        ForeignKeyConstraint(["activation_decision_id", "activation_decision_record_hash"], ["activation_decisions.activation_decision_id", "activation_decisions.record_hash"], name="fk_normative_activations_exact_decision", ondelete="RESTRICT"), ForeignKeyConstraint(["activation_execution_id"], ["activation_executions.activation_execution_id"], name="fk_normative_activations_execution", ondelete="RESTRICT"),
        UniqueConstraint("record_hash", name="uq_normative_activations_record_hash"), CheckConstraint("subject_type IN ('rule_version','normative_relation_version')", name="ck_normative_activations_subject_type"), CheckConstraint("state IN ('active','suspended','deactivated','expired','revoked')", name="ck_normative_activations_state"), CheckConstraint("length(activation_decision_record_hash)=64 AND length(subject_hash)=64 AND length(review_record_hash)=64 AND length(scope_hash)=64 AND length(record_hash)=64", name="ck_normative_activations_hashes"),
    )
    normative_activation_id = Column(String(64), primary_key=True); activation_decision_id = Column(String(64), nullable=False); activation_decision_record_hash = Column(String(64), nullable=False); activation_execution_id = Column(String(64), nullable=False); subject_type = Column(String(32), nullable=False); subject_id = Column(String(64), nullable=False); subject_version = Column(Integer, nullable=False); subject_hash = Column(String(64), nullable=False); review_record_id = Column(String(64), nullable=False); review_record_hash = Column(String(64), nullable=False); domain = Column(String(255), nullable=False); modality = Column(String(64), nullable=False); resolver_scope = Column(JSON, nullable=False); operational_interval = Column(JSON, nullable=False); scope_hash = Column(String(64), nullable=False); activation_generation_id = Column(String(64), nullable=False); activated_at = Column(DateTime(timezone=True), nullable=False); state = Column(String(16), nullable=False); technical_actor = Column(String(255), nullable=False); provenance = Column(JSON, nullable=False); record_hash = Column(String(64), nullable=False)


class ActivationGeneration(Base):
    __tablename__ = "activation_generations"
    __table_args__ = (
        ForeignKeyConstraint(["previous_activation_generation_id", "previous_activation_generation_record_hash"], ["activation_generations.activation_generation_id", "activation_generations.record_hash"], name="fk_activation_generations_previous", ondelete="RESTRICT"), ForeignKeyConstraint(["activation_execution_id"], ["activation_executions.activation_execution_id"], name="fk_activation_generations_execution", ondelete="RESTRICT"), ForeignKeyConstraint(["activation_decision_id", "activation_decision_record_hash"], ["activation_decisions.activation_decision_id", "activation_decisions.record_hash"], name="fk_activation_generations_exact_decision", ondelete="RESTRICT"), ForeignKeyConstraint(["activation_execution_id", "activation_decision_id", "activation_decision_record_hash"], ["activation_executions.activation_execution_id", "activation_executions.activation_decision_id", "activation_executions.activation_decision_record_hash"], name="fk_activation_generations_exact_execution_decision", match="SIMPLE", onupdate="RESTRICT", ondelete="RESTRICT", deferrable=False, initially="IMMEDIATE"),
        UniqueConstraint("record_hash", name="uq_activation_generations_record_hash"), UniqueConstraint("scope_hash", "composition_hash", name="uq_activation_generations_content"), CheckConstraint("length(scope_hash)=64 AND length(composition_hash)=64 AND length(target_manifest_hash)=64 AND length(record_hash)=64", name="ck_activation_generations_hashes"),
    )
    activation_generation_id = Column(String(64), primary_key=True); previous_activation_generation_id = Column(String(64), nullable=True); previous_activation_generation_record_hash = Column(String(64), nullable=True); activation_execution_id = Column(String(64), nullable=False, unique=True); activation_decision_id = Column(String(64), nullable=False); activation_decision_record_hash = Column(String(64), nullable=False); target_manifest_hash = Column(String(64), nullable=False); scope_descriptor = Column(JSON, nullable=False); scope_hash = Column(String(64), nullable=False); composition_manifest = Column(JSON, nullable=False); composition_hash = Column(String(64), nullable=False); policy_bindings = Column(JSON, nullable=False); coverage_binding = Column(JSON, nullable=False); continuity_binding = Column(JSON, nullable=False); precedence_binding = Column(JSON, nullable=False); gates_evidence = Column(JSON, nullable=False); is_complete = Column(Boolean, nullable=False); created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now()); effective_from = Column(DateTime(timezone=True), nullable=False); provenance = Column(JSON, nullable=False); record_hash = Column(String(64), nullable=False)


class GenerationFenceRecord(Base):
    __tablename__ = "generation_fence_records"
    __table_args__ = (
        ForeignKeyConstraint(["activation_generation_id", "activation_generation_record_hash"], ["activation_generations.activation_generation_id", "activation_generations.record_hash"], name="fk_generation_fences_exact_generation", ondelete="RESTRICT"),
        ForeignKeyConstraint(["activation_execution_id", "activation_execution_record_hash"], ["activation_executions.activation_execution_id", "activation_executions.record_hash"], name="fk_generation_fences_exact_execution", ondelete="RESTRICT"),
        ForeignKeyConstraint(["previous_generation_fence_record_id", "previous_generation_fence_record_hash"], ["generation_fence_records.generation_fence_record_id", "generation_fence_records.record_hash"], name="fk_generation_fences_exact_previous", ondelete="RESTRICT"),
        ForeignKeyConstraint(["source_event_id", "source_event_record_hash"], ["outbox_event_records.outbox_event_id", "outbox_event_records.record_hash"], name="fk_generation_fences_exact_source_event", ondelete="RESTRICT"),
        UniqueConstraint("generation_fence_record_id", "record_hash", name="uq_generation_fences_exact"), UniqueConstraint("scope_hash", "generation_sequence", name="uq_generation_fences_scope_sequence"), UniqueConstraint("previous_generation_fence_record_id", name="uq_generation_fences_successor"), UniqueConstraint("scope_hash", "fencing_token", name="uq_generation_fences_scope_token"),
        CheckConstraint("generation_sequence > 0 AND fencing_token > 0", name="ck_generation_fences_positive"), CheckConstraint("length(scope_hash)=64 AND length(activation_generation_record_hash)=64 AND length(activation_execution_record_hash)=64 AND length(publisher_lease_record_hash)=64 AND length(composition_hash)=64 AND length(source_event_record_hash)=64 AND length(record_hash)=64", name="ck_generation_fences_hashes"),
    )
    generation_fence_record_id = Column(String(64), primary_key=True); scope_hash = Column(String(64), nullable=False); generation_sequence = Column(Integer, nullable=False); fencing_token = Column(Integer, nullable=False); activation_generation_id = Column(String(64), nullable=False); activation_generation_record_hash = Column(String(64), nullable=False); activation_execution_id = Column(String(64), nullable=False); activation_execution_record_hash = Column(String(64), nullable=False); publisher_lease_id = Column(String(64), nullable=False); publisher_lease_record_hash = Column(String(64), nullable=False); composition_hash = Column(String(64), nullable=False); previous_generation_fence_record_id = Column(String(64), nullable=True); previous_generation_fence_record_hash = Column(String(64), nullable=True); source_event_id = Column(String(64), nullable=False); source_event_record_hash = Column(String(64), nullable=False); published_at = Column(DateTime(timezone=True), nullable=False); publisher = Column(String(255), nullable=False); provenance = Column(JSON, nullable=False); record_hash = Column(String(64), nullable=False)


class ConsumerContractVersion(Base):
    __tablename__ = "consumer_contract_versions"
    __table_args__ = (
        UniqueConstraint("consumer_id", "consumer_contract_version", "consumer_contract_hash", name="uq_consumer_contracts_exact"), UniqueConstraint("record_hash", name="uq_consumer_contracts_record_hash"),
        CheckConstraint("consumer_contract_version > 0 AND supported_protocol_version > 0 AND supported_generation_schema_version > 0", name="ck_consumer_contracts_versions_positive"), CheckConstraint("consumer_type IN ('service','replica','batch','interactive')", name="ck_consumer_contracts_type"), CheckConstraint("length(consumer_contract_hash)=64 AND length(allowed_scope_hash)=64 AND length(record_hash)=64", name="ck_consumer_contracts_hashes"),
    )
    consumer_id = Column(String(64), primary_key=True); consumer_contract_version = Column(Integer, primary_key=True); consumer_contract_hash = Column(String(64), nullable=False); consumer_type = Column(String(16), nullable=False); supported_protocol_version = Column(Integer, nullable=False); supported_generation_schema_version = Column(Integer, nullable=False); allowed_scope_descriptor = Column(JSON, nullable=False); allowed_scope_hash = Column(String(64), nullable=False); compatibility_rules = Column(JSON, nullable=False); freshness_policy_binding = Column(JSON, nullable=False); security_policy_binding = Column(JSON, nullable=False); created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now()); provenance = Column(JSON, nullable=False); record_hash = Column(String(64), nullable=False)


class ConsumerApplicationRecord(Base):
    __tablename__ = "consumer_application_records"
    __table_args__ = (
        ForeignKeyConstraint(["consumer_id", "consumer_contract_version", "consumer_contract_hash"], ["consumer_contract_versions.consumer_id", "consumer_contract_versions.consumer_contract_version", "consumer_contract_versions.consumer_contract_hash"], name="fk_consumer_applications_exact_contract", ondelete="RESTRICT"), ForeignKeyConstraint(["generation_fence_record_id", "generation_fence_record_hash"], ["generation_fence_records.generation_fence_record_id", "generation_fence_records.record_hash"], name="fk_consumer_applications_exact_fence", ondelete="RESTRICT"), ForeignKeyConstraint(["activation_generation_id", "activation_generation_record_hash"], ["activation_generations.activation_generation_id", "activation_generations.record_hash"], name="fk_consumer_applications_exact_generation", ondelete="RESTRICT"), ForeignKeyConstraint(["previous_replica_checkpoint_record_id", "previous_replica_checkpoint_record_hash"], ["replica_checkpoint_records.replica_checkpoint_record_id", "replica_checkpoint_records.record_hash"], name="fk_consumer_applications_exact_previous_checkpoint", ondelete="RESTRICT", use_alter=True), ForeignKeyConstraint(["duplicate_of_consumer_application_record_id", "duplicate_of_consumer_application_record_hash"], ["consumer_application_records.consumer_application_record_id", "consumer_application_records.record_hash"], name="fk_consumer_applications_exact_duplicate", ondelete="RESTRICT"), ForeignKeyConstraint(["duplicate_of_replica_checkpoint_record_id", "duplicate_of_replica_checkpoint_record_hash"], ["replica_checkpoint_records.replica_checkpoint_record_id", "replica_checkpoint_records.record_hash"], name="fk_consumer_applications_exact_duplicate_checkpoint", ondelete="RESTRICT", use_alter=True),
        UniqueConstraint("consumer_application_record_id", "record_hash", name="uq_consumer_applications_exact"), UniqueConstraint("consumer_id", "replica_id", "replica_instance_id", "attempt_number", name="uq_consumer_applications_attempt"),
        CheckConstraint("attempt_number > 0 AND generation_sequence > 0 AND fencing_token > 0", name="ck_consumer_applications_positive"), CheckConstraint("application_result IN ('pending','validating','applied','duplicate_exact','rejected_stale','rejected_gap','rejected_divergent','rejected_incompatible','failed','cancelled')", name="ck_consumer_applications_result"), CheckConstraint("length(consumer_contract_hash)=64 AND length(scope_hash)=64 AND length(generation_fence_record_hash)=64 AND length(activation_generation_record_hash)=64 AND length(composition_hash)=64 AND length(record_hash)=64", name="ck_consumer_applications_hashes"),
    )
    consumer_application_record_id = Column(String(64), primary_key=True); consumer_id = Column(String(64), nullable=False); replica_id = Column(String(64), nullable=False); replica_instance_id = Column(String(64), nullable=False); consumer_contract_version = Column(Integer, nullable=False); consumer_contract_hash = Column(String(64), nullable=False); scope_hash = Column(String(64), nullable=False); generation_fence_record_id = Column(String(64), nullable=False); generation_fence_record_hash = Column(String(64), nullable=False); generation_sequence = Column(Integer, nullable=False); fencing_token = Column(Integer, nullable=False); activation_generation_id = Column(String(64), nullable=False); activation_generation_record_hash = Column(String(64), nullable=False); composition_hash = Column(String(64), nullable=False); previous_replica_checkpoint_record_id = Column(String(64), nullable=True); previous_replica_checkpoint_record_hash = Column(String(64), nullable=True); duplicate_of_consumer_application_record_id = Column(String(64), nullable=True); duplicate_of_consumer_application_record_hash = Column(String(64), nullable=True); duplicate_of_replica_checkpoint_record_id = Column(String(64), nullable=True); duplicate_of_replica_checkpoint_record_hash = Column(String(64), nullable=True); attempt_number = Column(Integer, nullable=False); application_result = Column(String(32), nullable=False); started_at = Column(DateTime(timezone=True), nullable=False); finished_at = Column(DateTime(timezone=True), nullable=True); structured_result = Column(JSON, nullable=True); structured_error = Column(JSON, nullable=True); provenance = Column(JSON, nullable=False); record_hash = Column(String(64), nullable=False)


class ReplicaCheckpointRecord(Base):
    __tablename__ = "replica_checkpoint_records"
    __table_args__ = (
        ForeignKeyConstraint(["consumer_application_record_id", "consumer_application_record_hash"], ["consumer_application_records.consumer_application_record_id", "consumer_application_records.record_hash"], name="fk_replica_checkpoints_exact_application", ondelete="RESTRICT"), ForeignKeyConstraint(["consumer_id", "consumer_contract_version", "consumer_contract_hash"], ["consumer_contract_versions.consumer_id", "consumer_contract_versions.consumer_contract_version", "consumer_contract_versions.consumer_contract_hash"], name="fk_replica_checkpoints_exact_contract", ondelete="RESTRICT"), ForeignKeyConstraint(["generation_fence_record_id", "generation_fence_record_hash"], ["generation_fence_records.generation_fence_record_id", "generation_fence_records.record_hash"], name="fk_replica_checkpoints_exact_fence", ondelete="RESTRICT"), ForeignKeyConstraint(["activation_generation_id", "activation_generation_record_hash"], ["activation_generations.activation_generation_id", "activation_generations.record_hash"], name="fk_replica_checkpoints_exact_generation", ondelete="RESTRICT"), ForeignKeyConstraint(["previous_replica_checkpoint_record_id", "previous_replica_checkpoint_record_hash"], ["replica_checkpoint_records.replica_checkpoint_record_id", "replica_checkpoint_records.record_hash"], name="fk_replica_checkpoints_exact_previous", ondelete="RESTRICT"),
        UniqueConstraint("replica_checkpoint_record_id", "record_hash", name="uq_replica_checkpoints_exact"), UniqueConstraint("consumer_application_record_id", name="uq_replica_checkpoints_application"), UniqueConstraint("previous_replica_checkpoint_record_id", name="uq_replica_checkpoints_successor"), UniqueConstraint("consumer_id", "replica_id", "replica_instance_id", "scope_hash", "generation_sequence", name="uq_replica_checkpoints_sequence"),
        CheckConstraint("generation_sequence > 0 AND fencing_token > 0", name="ck_replica_checkpoints_positive"), CheckConstraint("length(consumer_contract_hash)=64 AND length(scope_hash)=64 AND length(generation_fence_record_hash)=64 AND length(activation_generation_record_hash)=64 AND length(composition_hash)=64 AND length(record_hash)=64", name="ck_replica_checkpoints_hashes"),
    )
    replica_checkpoint_record_id = Column(String(64), primary_key=True); consumer_application_record_id = Column(String(64), nullable=False); consumer_application_record_hash = Column(String(64), nullable=False); consumer_id = Column(String(64), nullable=False); replica_id = Column(String(64), nullable=False); replica_instance_id = Column(String(64), nullable=False); consumer_contract_version = Column(Integer, nullable=False); consumer_contract_hash = Column(String(64), nullable=False); scope_hash = Column(String(64), nullable=False); generation_fence_record_id = Column(String(64), nullable=False); generation_fence_record_hash = Column(String(64), nullable=False); generation_sequence = Column(Integer, nullable=False); fencing_token = Column(Integer, nullable=False); activation_generation_id = Column(String(64), nullable=False); activation_generation_record_hash = Column(String(64), nullable=False); composition_hash = Column(String(64), nullable=False); previous_replica_checkpoint_record_id = Column(String(64), nullable=True); previous_replica_checkpoint_record_hash = Column(String(64), nullable=True); applied_at = Column(DateTime(timezone=True), nullable=False); provenance = Column(JSON, nullable=False); record_hash = Column(String(64), nullable=False)


class CalculationBundle(Base):
    __tablename__ = "calculation_bundles"
    __table_args__ = (
        ForeignKeyConstraint(["generation_fence_record_id", "generation_fence_record_hash"], ["generation_fence_records.generation_fence_record_id", "generation_fence_records.record_hash"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["activation_generation_id", "activation_generation_record_hash"], ["activation_generations.activation_generation_id", "activation_generations.record_hash"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["consumer_id", "consumer_contract_version", "consumer_contract_hash"], ["consumer_contract_versions.consumer_id", "consumer_contract_versions.consumer_contract_version", "consumer_contract_versions.consumer_contract_hash"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["consumer_application_record_id", "consumer_application_record_hash"], ["consumer_application_records.consumer_application_record_id", "consumer_application_records.record_hash"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["replica_checkpoint_record_id", "replica_checkpoint_record_hash"], ["replica_checkpoint_records.replica_checkpoint_record_id", "replica_checkpoint_records.record_hash"], ondelete="RESTRICT"),
        UniqueConstraint("calculation_bundle_id", "calculation_bundle_hash"), UniqueConstraint("record_hash"),
        CheckConstraint("calculation_bundle_schema_version > 0 AND generation_sequence > 0 AND fencing_token > 0"),
    )
    calculation_bundle_id = Column(String(64), primary_key=True); calculation_bundle_schema_version = Column(Integer, nullable=False); calculation_bundle_hash = Column(String(64), nullable=False); scope_hash = Column(String(64), nullable=False); generation_fence_record_id = Column(String(64), nullable=False); generation_fence_record_hash = Column(String(64), nullable=False); generation_sequence = Column(Integer, nullable=False); fencing_token = Column(Integer, nullable=False); activation_generation_id = Column(String(64), nullable=False); activation_generation_record_hash = Column(String(64), nullable=False); composition_hash = Column(String(64), nullable=False); consumer_id = Column(String(64), nullable=False); consumer_contract_version = Column(Integer, nullable=False); consumer_contract_hash = Column(String(64), nullable=False); replica_id = Column(String(64), nullable=False); replica_instance_id = Column(String(64), nullable=False); consumer_application_record_id = Column(String(64), nullable=False); consumer_application_record_hash = Column(String(64), nullable=False); replica_checkpoint_record_id = Column(String(64), nullable=False); replica_checkpoint_record_hash = Column(String(64), nullable=False); calculation_subject_reference = Column(JSON, nullable=False); input_snapshot_manifest = Column(JSON, nullable=False); normative_member_manifest = Column(JSON, nullable=False); policy_binding_manifest = Column(JSON, nullable=False); coverage_binding = Column(JSON, nullable=False); continuity_binding = Column(JSON, nullable=False); precedence_binding = Column(JSON, nullable=False); gates_evidence = Column(JSON, nullable=False); engine_binding = Column(JSON, nullable=False); runtime_binding = Column(JSON, nullable=False); canonical_serialization_binding = Column(JSON, nullable=False); evaluation_instant = Column(DateTime(timezone=True), nullable=False); deterministic_seed_binding = Column(JSON, nullable=False); created_at = Column(DateTime(timezone=True), nullable=False); creator = Column(String(255), nullable=False); provenance = Column(JSON, nullable=False); record_hash = Column(String(64), nullable=False)


class CalculationExecutionRecord(Base):
    __tablename__ = "calculation_execution_records"
    __table_args__ = (ForeignKeyConstraint(["calculation_bundle_id", "calculation_bundle_hash"], ["calculation_bundles.calculation_bundle_id", "calculation_bundles.calculation_bundle_hash"], ondelete="RESTRICT"), UniqueConstraint("calculation_execution_record_id", "record_hash"), UniqueConstraint("calculation_bundle_id", "attempt_number"), CheckConstraint("attempt_number > 0 AND fencing_token > 0"), CheckConstraint("state IN ('pending','validating','running','completed','rejected_incomplete','rejected_divergent','rejected_incompatible','failed','cancelled')"))
    calculation_execution_record_id = Column(String(64), primary_key=True); calculation_bundle_id = Column(String(64), nullable=False); calculation_bundle_hash = Column(String(64), nullable=False); attempt_number = Column(Integer, nullable=False); fencing_token = Column(Integer, nullable=False); state = Column(String(32), nullable=False); executor = Column(String(255), nullable=False); engine_artifact_id = Column(String(64), nullable=False); engine_artifact_hash = Column(String(64), nullable=False); runtime_artifact_id = Column(String(64), nullable=False); runtime_artifact_hash = Column(String(64), nullable=False); started_at = Column(DateTime(timezone=True), nullable=False); finished_at = Column(DateTime(timezone=True), nullable=True); structured_result = Column(JSON, nullable=True); structured_error = Column(JSON, nullable=True); provenance = Column(JSON, nullable=False); record_hash = Column(String(64), nullable=False)


class CalculationResultRecord(Base):
    __tablename__ = "calculation_result_records"
    __table_args__ = (ForeignKeyConstraint(["calculation_execution_record_id", "calculation_execution_record_hash"], ["calculation_execution_records.calculation_execution_record_id", "calculation_execution_records.record_hash"], ondelete="RESTRICT"), ForeignKeyConstraint(["calculation_bundle_id", "calculation_bundle_hash"], ["calculation_bundles.calculation_bundle_id", "calculation_bundles.calculation_bundle_hash"], ondelete="RESTRICT"), UniqueConstraint("calculation_result_record_id", "record_hash"), UniqueConstraint("calculation_execution_record_id"), CheckConstraint("result_schema_version > 0"))
    calculation_result_record_id = Column(String(64), primary_key=True); calculation_execution_record_id = Column(String(64), nullable=False); calculation_execution_record_hash = Column(String(64), nullable=False); calculation_bundle_id = Column(String(64), nullable=False); calculation_bundle_hash = Column(String(64), nullable=False); result_schema_version = Column(Integer, nullable=False); result_payload_reference = Column(JSON, nullable=False); result_payload_hash = Column(String(64), nullable=False); calculation_trace_reference = Column(JSON, nullable=False); calculation_trace_hash = Column(String(64), nullable=False); decision_trace_reference = Column(JSON, nullable=False); decision_trace_hash = Column(String(64), nullable=False); canonical_result_hash = Column(String(64), nullable=False); completed_at = Column(DateTime(timezone=True), nullable=False); provenance = Column(JSON, nullable=False); record_hash = Column(String(64), nullable=False)


class ReplayExecutionRecord(Base):
    __tablename__ = "replay_execution_records"
    __table_args__ = (ForeignKeyConstraint(["calculation_bundle_id", "calculation_bundle_hash"], ["calculation_bundles.calculation_bundle_id", "calculation_bundles.calculation_bundle_hash"], ondelete="RESTRICT"), ForeignKeyConstraint(["original_calculation_execution_record_id", "original_calculation_execution_record_hash"], ["calculation_execution_records.calculation_execution_record_id", "calculation_execution_records.record_hash"], ondelete="RESTRICT"), ForeignKeyConstraint(["original_calculation_result_record_id", "original_calculation_result_record_hash"], ["calculation_result_records.calculation_result_record_id", "calculation_result_records.record_hash"], ondelete="RESTRICT"), UniqueConstraint("replay_execution_record_id", "record_hash"), UniqueConstraint("original_calculation_result_record_id", "attempt_number"), CheckConstraint("attempt_number > 0"), CheckConstraint("state IN ('pending','validating','running','completed','rejected_incomplete','rejected_divergent','rejected_incompatible','failed','cancelled')"))
    replay_execution_record_id = Column(String(64), primary_key=True); calculation_bundle_id = Column(String(64), nullable=False); calculation_bundle_hash = Column(String(64), nullable=False); original_calculation_execution_record_id = Column(String(64), nullable=False); original_calculation_execution_record_hash = Column(String(64), nullable=False); original_calculation_result_record_id = Column(String(64), nullable=False); original_calculation_result_record_hash = Column(String(64), nullable=False); original_canonical_result_hash = Column(String(64), nullable=False); replay_engine_artifact_id = Column(String(64), nullable=False); replay_engine_artifact_hash = Column(String(64), nullable=False); replay_runtime_artifact_id = Column(String(64), nullable=False); replay_runtime_artifact_hash = Column(String(64), nullable=False); replay_dependency_manifest_hash = Column(String(64), nullable=False); replay_platform_contract_hash = Column(String(64), nullable=False); replay_canonical_serialization_contract_hash = Column(String(64), nullable=False); replay_result_schema_version = Column(Integer, nullable=False); replay_evaluation_instant = Column(DateTime(timezone=True), nullable=False); replay_deterministic_seed_binding_hash = Column(String(64), nullable=False); attempt_number = Column(Integer, nullable=False); state = Column(String(32), nullable=False); started_at = Column(DateTime(timezone=True), nullable=False); finished_at = Column(DateTime(timezone=True), nullable=True); replay_result_payload_hash = Column(String(64), nullable=True); replay_calculation_trace_hash = Column(String(64), nullable=True); replay_decision_trace_hash = Column(String(64), nullable=True); replay_canonical_result_hash = Column(String(64), nullable=True); structured_result = Column(JSON, nullable=True); structured_error = Column(JSON, nullable=True); provenance = Column(JSON, nullable=False); record_hash = Column(String(64), nullable=False)


class ReplayVerificationRecord(Base):
    __tablename__ = "replay_verification_records"
    __table_args__ = (ForeignKeyConstraint(["replay_execution_record_id", "replay_execution_record_hash"], ["replay_execution_records.replay_execution_record_id", "replay_execution_records.record_hash"], ondelete="RESTRICT"), ForeignKeyConstraint(["calculation_bundle_id", "calculation_bundle_hash"], ["calculation_bundles.calculation_bundle_id", "calculation_bundles.calculation_bundle_hash"], ondelete="RESTRICT"), ForeignKeyConstraint(["original_calculation_result_record_id", "original_calculation_result_record_hash"], ["calculation_result_records.calculation_result_record_id", "calculation_result_records.record_hash"], ondelete="RESTRICT"), UniqueConstraint("replay_execution_record_id"), UniqueConstraint("record_hash"), CheckConstraint("verification_outcome IN ('match','mismatch','inconclusive')"))
    replay_verification_record_id = Column(String(64), primary_key=True); replay_execution_record_id = Column(String(64), nullable=False); replay_execution_record_hash = Column(String(64), nullable=False); calculation_bundle_id = Column(String(64), nullable=False); calculation_bundle_hash = Column(String(64), nullable=False); original_calculation_result_record_id = Column(String(64), nullable=False); original_calculation_result_record_hash = Column(String(64), nullable=False); original_canonical_result_hash = Column(String(64), nullable=False); replay_canonical_result_hash = Column(String(64), nullable=True); result_payload_match = Column(Boolean, nullable=False); calculation_trace_match = Column(Boolean, nullable=False); decision_trace_match = Column(Boolean, nullable=False); verification_outcome = Column(String(16), nullable=False); mismatch_manifest = Column(JSON, nullable=False); verified_at = Column(DateTime(timezone=True), nullable=False); verifier = Column(String(255), nullable=False); provenance = Column(JSON, nullable=False); record_hash = Column(String(64), nullable=False)


class CredentialBindingVersion(Base):
    __tablename__ = "credential_binding_versions"
    __table_args__ = (UniqueConstraint("credential_binding_id", "credential_binding_version", name="uq_credential_binding_versions_identity"), UniqueConstraint("credential_binding_id", "credential_binding_version", "credential_binding_hash", name="uq_credential_binding_versions_exact"), UniqueConstraint("record_hash"), CheckConstraint("credential_binding_version > 0"), CheckConstraint("valid_until IS NULL OR valid_until > valid_from"))
    credential_binding_id = Column(String(64), primary_key=True); credential_binding_version = Column(Integer, primary_key=True); credential_binding_hash = Column(String(64), nullable=False); credential_type = Column(String(64), nullable=False); secret_provider_binding = Column(JSON, nullable=False); opaque_secret_reference_id = Column(String(255), nullable=False); opaque_secret_version_reference_id = Column(String(255), nullable=False); permitted_purpose = Column(String(64), nullable=False); permitted_operation = Column(String(64), nullable=False); permitted_source_scope = Column(JSON, nullable=False); permitted_tenant_scope = Column(JSON, nullable=True); acquisition_contract_binding = Column(JSON, nullable=False); secret_access_policy_binding = Column(JSON, nullable=False); security_policy_binding = Column(JSON, nullable=False); sanitization_policy_binding = Column(JSON, nullable=False); valid_from = Column(DateTime(timezone=True), nullable=False); valid_until = Column(DateTime(timezone=True), nullable=True); created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now()); creator = Column(String(255), nullable=False); provenance = Column(JSON, nullable=False); record_hash = Column(String(64), nullable=False)


class CredentialLifecycleEventRecord(Base):
    __tablename__ = "credential_lifecycle_event_records"
    __table_args__ = (ForeignKeyConstraint(["credential_binding_id", "credential_binding_version", "credential_binding_hash"], ["credential_binding_versions.credential_binding_id", "credential_binding_versions.credential_binding_version", "credential_binding_versions.credential_binding_hash"], ondelete="RESTRICT"), ForeignKeyConstraint(["previous_lifecycle_event_record_id", "previous_lifecycle_event_record_hash"], ["credential_lifecycle_event_records.credential_lifecycle_event_record_id", "credential_lifecycle_event_records.record_hash"], ondelete="RESTRICT"), UniqueConstraint("previous_lifecycle_event_record_id"), UniqueConstraint("credential_lifecycle_event_record_id", "record_hash"), CheckConstraint("lifecycle_event IN ('activated','suspended','resumed','revoked','expired','rotated')"))
    credential_lifecycle_event_record_id = Column(String(64), primary_key=True); credential_binding_id = Column(String(64), nullable=False); credential_binding_version = Column(Integer, nullable=False); credential_binding_hash = Column(String(64), nullable=False); lifecycle_event = Column(String(16), nullable=False); previous_lifecycle_event_record_id = Column(String(64), nullable=True); previous_lifecycle_event_record_hash = Column(String(64), nullable=True); replacement_credential_binding_id = Column(String(64), nullable=True); replacement_credential_binding_version = Column(Integer, nullable=True); replacement_credential_binding_hash = Column(String(64), nullable=True); effective_at = Column(DateTime(timezone=True), nullable=False); actor = Column(String(255), nullable=False); institutional_role = Column(String(64), nullable=False); reason_code = Column(String(64), nullable=False); provenance = Column(JSON, nullable=False); record_hash = Column(String(64), nullable=False)


class SecretAccessExecutionRecord(Base):
    __tablename__ = "secret_access_execution_records"
    __table_args__ = (ForeignKeyConstraint(["credential_binding_id", "credential_binding_version", "credential_binding_hash"], ["credential_binding_versions.credential_binding_id", "credential_binding_versions.credential_binding_version", "credential_binding_versions.credential_binding_hash"], ondelete="RESTRICT"), ForeignKeyConstraint(["credential_lifecycle_event_record_id", "credential_lifecycle_event_record_hash"], ["credential_lifecycle_event_records.credential_lifecycle_event_record_id", "credential_lifecycle_event_records.record_hash"], ondelete="RESTRICT"), UniqueConstraint("secret_access_execution_record_id", "record_hash"), CheckConstraint("access_state IN ('pending','validating','authorized','accessed','rejected_inactive','rejected_scope','rejected_policy','rejected_divergent','failed','cancelled')"), CheckConstraint("attempt_number > 0 AND fencing_token > 0"))
    secret_access_execution_record_id = Column(String(64), primary_key=True); acquisition_execution_id = Column(String(64), nullable=False); acquisition_execution_record_hash = Column(String(64), nullable=False); credential_binding_id = Column(String(64), nullable=False); credential_binding_version = Column(Integer, nullable=False); credential_binding_hash = Column(String(64), nullable=False); credential_lifecycle_event_record_id = Column(String(64), nullable=False); credential_lifecycle_event_record_hash = Column(String(64), nullable=False); secret_provider_id = Column(String(64), nullable=False); secret_provider_version = Column(Integer, nullable=False); secret_provider_artifact_hash = Column(String(64), nullable=False); opaque_secret_reference_id = Column(String(255), nullable=False); opaque_secret_version_reference_id = Column(String(255), nullable=False); requested_purpose = Column(String(64), nullable=False); requested_operation = Column(String(64), nullable=False); requested_source_scope = Column(JSON, nullable=False); requested_tenant_scope = Column(JSON, nullable=True); attempt_number = Column(Integer, nullable=False); actor_or_worker = Column(String(255), nullable=False); lease_id = Column(String(64), nullable=False); lease_record_hash = Column(String(64), nullable=False); fencing_token = Column(Integer, nullable=False); access_state = Column(String(32), nullable=False); started_at = Column(DateTime(timezone=True), nullable=False); finished_at = Column(DateTime(timezone=True), nullable=True); structured_result = Column(JSON, nullable=True); structured_error = Column(JSON, nullable=True); provenance = Column(JSON, nullable=False); record_hash = Column(String(64), nullable=False)


class CredentialUseRecord(Base):
    __tablename__ = "credential_use_records"
    __table_args__ = (ForeignKeyConstraint(["previous_credential_use_record_id", "previous_credential_use_record_hash"], ["credential_use_records.credential_use_record_id", "credential_use_records.record_hash"], ondelete="RESTRICT"), ForeignKeyConstraint(["secret_access_execution_record_id", "secret_access_execution_record_hash"], ["secret_access_execution_records.secret_access_execution_record_id", "secret_access_execution_records.record_hash"], ondelete="RESTRICT"), UniqueConstraint("previous_credential_use_record_id"), UniqueConstraint("credential_use_record_id", "record_hash"), CheckConstraint("use_outcome IN ('dispatched','succeeded','rejected_by_source','transport_failed','cancelled_before_dispatch','indeterminate_after_dispatch')"))
    credential_use_record_id = Column(String(64), primary_key=True); credential_use_chain_id = Column(String(64), nullable=False); previous_credential_use_record_id = Column(String(64), nullable=True); previous_credential_use_record_hash = Column(String(64), nullable=True); acquisition_execution_id = Column(String(64), nullable=False); acquisition_execution_record_hash = Column(String(64), nullable=False); secret_access_execution_record_id = Column(String(64), nullable=False); secret_access_execution_record_hash = Column(String(64), nullable=False); credential_binding_id = Column(String(64), nullable=False); credential_binding_version = Column(Integer, nullable=False); credential_binding_hash = Column(String(64), nullable=False); credential_lifecycle_event_record_id = Column(String(64), nullable=False); credential_lifecycle_event_record_hash = Column(String(64), nullable=False); request_contract_id = Column(String(64), nullable=False); request_contract_version = Column(Integer, nullable=False); request_contract_hash = Column(String(64), nullable=False); sanitized_request_fingerprint = Column(String(64), nullable=False); sanitized_request_fingerprint_schema_version = Column(Integer, nullable=False); sanitized_request_canonicalization_contract_id = Column(String(64), nullable=False); sanitized_request_canonicalization_contract_version = Column(Integer, nullable=False); sanitized_request_canonicalization_contract_hash = Column(String(64), nullable=False); source_scope = Column(JSON, nullable=False); tenant_scope = Column(JSON, nullable=True); dispatch_attempt_number = Column(Integer, nullable=False); dispatched_at = Column(DateTime(timezone=True), nullable=True); finished_at = Column(DateTime(timezone=True), nullable=False); use_outcome = Column(String(32), nullable=False); source_response_observed = Column(Boolean, nullable=False); structured_result = Column(JSON, nullable=True); structured_error = Column(JSON, nullable=True); provenance = Column(JSON, nullable=False); record_hash = Column(String(64), nullable=False)


class SanitizedAcquisitionReceipt(Base):
    __tablename__ = "sanitized_acquisition_receipts"
    __table_args__ = (ForeignKeyConstraint(["credential_use_record_id", "credential_use_record_hash"], ["credential_use_records.credential_use_record_id", "credential_use_records.record_hash"], ondelete="RESTRICT"), UniqueConstraint("sanitized_acquisition_receipt_id", "sanitized_acquisition_receipt_hash"), CheckConstraint("acquisition_outcome IN ('acquired','source_rejected','no_content_valid','transport_failed','indeterminate','cancelled_before_dispatch')"))
    sanitized_acquisition_receipt_id = Column(String(64), primary_key=True); sanitized_acquisition_receipt_schema_version = Column(Integer, nullable=False); sanitized_acquisition_receipt_hash = Column(String(64), nullable=False); acquisition_execution_id = Column(String(64), nullable=False); acquisition_execution_record_hash = Column(String(64), nullable=False); credential_use_record_id = Column(String(64), nullable=False); credential_use_record_hash = Column(String(64), nullable=False); credential_binding_id = Column(String(64), nullable=False); credential_binding_version = Column(Integer, nullable=False); credential_binding_hash = Column(String(64), nullable=False); source_identity_binding = Column(JSON, nullable=False); source_scope = Column(JSON, nullable=False); tenant_scope = Column(JSON, nullable=True); request_contract_id = Column(String(64), nullable=False); request_contract_version = Column(Integer, nullable=False); request_contract_hash = Column(String(64), nullable=False); sanitized_request_manifest = Column(JSON, nullable=False); sanitized_request_fingerprint = Column(String(64), nullable=False); sanitized_request_fingerprint_schema_version = Column(Integer, nullable=False); sanitized_request_canonicalization_contract_id = Column(String(64), nullable=False); sanitized_request_canonicalization_contract_version = Column(Integer, nullable=False); sanitized_request_canonicalization_contract_hash = Column(String(64), nullable=False); response_status_class = Column(String(32), nullable=True); sanitized_response_metadata = Column(JSON, nullable=False); acquired_content_reference = Column(JSON, nullable=True); acquired_content_hash = Column(String(64), nullable=True); transport_evidence_manifest = Column(JSON, nullable=False); redaction_manifest = Column(JSON, nullable=False); sanitization_policy_binding = Column(JSON, nullable=False); acquisition_started_at = Column(DateTime(timezone=True), nullable=False); dispatch_observed_at = Column(DateTime(timezone=True), nullable=True); response_observed_at = Column(DateTime(timezone=True), nullable=True); receipt_created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now()); acquisition_outcome = Column(String(32), nullable=False); creator = Column(String(255), nullable=False); provenance = Column(JSON, nullable=False); record_hash = Column(String(64), nullable=False)


class SanitizationVerificationRecord(Base):
    __tablename__ = "sanitization_verification_records"
    __table_args__ = (ForeignKeyConstraint(["sanitized_acquisition_receipt_id", "sanitized_acquisition_receipt_hash"], ["sanitized_acquisition_receipts.sanitized_acquisition_receipt_id", "sanitized_acquisition_receipts.sanitized_acquisition_receipt_hash"], ondelete="RESTRICT"), UniqueConstraint("record_hash"), CheckConstraint("verification_outcome IN ('verified_sanitized','verified_violation','inconclusive')"))
    sanitization_verification_record_id = Column(String(64), primary_key=True); sanitized_acquisition_receipt_id = Column(String(64), nullable=False); sanitized_acquisition_receipt_hash = Column(String(64), nullable=False); sanitization_policy_id = Column(String(64), nullable=False); sanitization_policy_version = Column(Integer, nullable=False); sanitization_policy_hash = Column(String(64), nullable=False); sanitization_policy_activation_id = Column(String(64), nullable=False); sanitization_policy_activation_record_hash = Column(String(64), nullable=False); verification_engine_id = Column(String(64), nullable=False); verification_engine_version = Column(Integer, nullable=False); verification_engine_hash = Column(String(64), nullable=False); inspected_component_manifest = Column(JSON, nullable=False); violation_manifest = Column(JSON, nullable=False); verification_outcome = Column(String(32), nullable=False); verified_at = Column(DateTime(timezone=True), nullable=False); verifier = Column(String(255), nullable=False); provenance = Column(JSON, nullable=False); record_hash = Column(String(64), nullable=False)


class OutboxEventRecord(Base):
    __tablename__ = "outbox_event_records"
    __table_args__ = (
        ForeignKeyConstraint(["activation_execution_id"], ["activation_executions.activation_execution_id"], name="fk_outbox_event_records_execution", ondelete="RESTRICT"), ForeignKeyConstraint(["activation_generation_id"], ["activation_generations.activation_generation_id"], name="fk_outbox_event_records_generation", ondelete="RESTRICT"), ForeignKeyConstraint(["activation_decision_id"], ["activation_decisions.activation_decision_id"], name="fk_outbox_event_records_decision", ondelete="RESTRICT"),
        UniqueConstraint("record_hash", name="uq_outbox_event_records_record_hash"), UniqueConstraint("outbox_event_id", "record_hash", name="uq_outbox_event_records_exact"), CheckConstraint("event_type IN ('activation_completed','activation_invalidated')", name="ck_outbox_event_records_type"), CheckConstraint("length(scope_hash)=64 AND length(composition_hash)=64 AND length(payload_hash)=64 AND length(record_hash)=64", name="ck_outbox_event_records_hashes"),
    )
    outbox_event_id = Column(String(64), primary_key=True); event_type = Column(String(32), nullable=False); activation_execution_id = Column(String(64), nullable=False); activation_generation_id = Column(String(64), nullable=False); activation_decision_id = Column(String(64), nullable=False); scope_hash = Column(String(64), nullable=False); composition_hash = Column(String(64), nullable=False); payload = Column(JSON, nullable=False); payload_hash = Column(String(64), nullable=False); provenance = Column(JSON, nullable=False); created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now()); record_hash = Column(String(64), nullable=False)


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


def _adr020_validate_extraction_run_insert(
    mapper,
    connection,
    target,
) -> None:
    expected_state = _EXTRACTION_EVENT_STATE.get(target.run_event)
    if expected_state is None or target.projected_state != expected_state:
        raise ValueError("ADR-020 invalid ExtractionRun event/state pair")

    _adr020_require_sha256(target.artifact_hash, "artifact_hash")
    _adr020_require_sha256(target.parameters_hash, "parameters_hash")
    _adr020_require_sha256(target.record_hash, "record_hash")

    if not str(target.extractor_id or "").strip():
        raise ValueError("ADR-020 extractor_id cannot be empty")
    if not str(target.extractor_version or "").strip():
        raise ValueError("ADR-020 extractor_version cannot be empty")
    if target.attempt_number is None or target.attempt_number <= 0:
        raise ValueError("ADR-020 attempt_number must be positive")
    if target.event_sequence is None or target.event_sequence <= 0:
        raise ValueError("ADR-020 event_sequence must be positive")

    if target.event_sequence == 1:
        if (
            target.run_event != "criacao"
            or target.projected_state != "pendente"
            or target.previous_extraction_run_record_id is not None
            or target.started_at is not None
            or target.finished_at is not None
        ):
            raise ValueError("ADR-020 invalid initial ExtractionRun event")
    elif target.previous_extraction_run_record_id is None:
        raise ValueError("ADR-020 ExtractionRun predecessor is required")

    gates = (
        (
            target.authenticity_verification_record_id,
            target.authenticity_predecessor_type,
            target.authenticity_predecessor_outcome,
            "authenticity",
        ),
        (
            target.integrity_verification_record_id,
            target.integrity_predecessor_type,
            target.integrity_predecessor_outcome,
            "integrity",
        ),
        (
            target.preservation_verification_record_id,
            target.preservation_predecessor_type,
            target.preservation_predecessor_outcome,
            "preservation",
        ),
    )

    has_any_gate = any(
        value is not None
        for record_id, gate_type, outcome, expected_type in gates
        for value in (record_id, gate_type, outcome)
    )

    has_all_favorable_gates = all(
        record_id is not None
        and gate_type == expected_type
        and outcome == "conclusivo_favoravel"
        for record_id, gate_type, outcome, expected_type in gates
    )

    if has_any_gate and not has_all_favorable_gates:
        raise ValueError(
            "ADR-020 ExtractionRun requires exact favorable verification gates"
        )

    if (
        target.projected_state
        in {"em_processamento", "concluida", "falhada"}
        and not has_all_favorable_gates
    ):
        raise ValueError(
            "ADR-020 ExtractionRun requires favorable verification gates"
        )

    if target.projected_state == "pendente":
        if (
            target.started_at is not None
            or target.finished_at is not None
            or target.structured_error is not None
        ):
            raise ValueError(
                "ADR-020 pending ExtractionRun cannot contain execution data"
            )

    if target.projected_state == "em_processamento":
        if target.started_at is None or target.finished_at is not None:
            raise ValueError(
                "ADR-020 processing ExtractionRun requires started_at only"
            )

    if target.projected_state in _EXTRACTION_TERMINAL_STATES:
        if target.finished_at is None:
            raise ValueError(
                "ADR-020 terminal ExtractionRun requires finished_at"
            )

    if target.projected_state == "falhada" and not target.structured_error:
        raise ValueError(
            "ADR-020 failed ExtractionRun requires structured_error"
        )

    if (
        target.started_at is not None
        and target.occurred_at is not None
        and target.started_at > target.occurred_at
    ):
        raise ValueError(
            "ADR-020 ExtractionRun started_at cannot follow occurred_at"
        )

    if target.finished_at is not None:
        if (
            target.started_at is not None
            and target.finished_at < target.started_at
        ):
            raise ValueError(
                "ADR-020 ExtractionRun finished_at precedes started_at"
            )
        if (
            target.occurred_at is not None
            and target.finished_at > target.occurred_at
        ):
            raise ValueError(
                "ADR-020 ExtractionRun finished_at cannot follow occurred_at"
            )


def _adr020_validate_extraction_result_insert(
    mapper,
    connection,
    target,
) -> None:
    if target.run_event != "conclusao" or target.run_state != "concluida":
        raise ValueError(
            "ADR-020 ExtractionResult requires exact concluded extraction run"
        )

    if target.outcome not in _EXTRACTION_OUTCOMES:
        raise ValueError("ADR-020 invalid ExtractionResult outcome")

    _adr020_require_sha256(target.artifact_hash, "artifact_hash")
    _adr020_require_sha256(target.parameters_hash, "parameters_hash")
    _adr020_require_sha256(target.record_hash, "record_hash")

    if not str(target.extractor_id or "").strip():
        raise ValueError("ADR-020 extractor_id cannot be empty")
    if not str(target.extractor_version or "").strip():
        raise ValueError("ADR-020 extractor_version cannot be empty")
    if target.attempt_number is None or target.attempt_number <= 0:
        raise ValueError("ADR-020 attempt_number must be positive")

    if not target.structured_content:
        raise ValueError(
            "ADR-020 ExtractionResult requires effective structured_content"
        )

def _adr020_validate_rule_version_insert(
    mapper,
    connection,
    target,
) -> None:
    _adr020_require_sha256(target.rule_hash, "rule_hash")
    _adr020_require_sha256(
        target.extraction_result_record_hash,
        "extraction_result_record_hash",
    )
    _adr020_require_sha256(target.record_hash, "record_hash")

    if target.rule_version is None or target.rule_version <= 0:
        raise ValueError("ADR-020 RuleVersion version must be positive")

    if not str(target.rule_id or "").strip():
        raise ValueError("ADR-020 RuleVersion rule_id cannot be empty")

    if not target.structured_content:
        raise ValueError(
            "ADR-020 RuleVersion requires structured_content"
        )

    if target.declared_material_validity is None:
        raise ValueError(
            "ADR-020 RuleVersion requires declared material validity"
        )

    if target.exact_precedence_policy_reference is None:
        raise ValueError(
            "ADR-020 RuleVersion requires exact precedence policy reference"
        )


def _adr020_validate_rule_review_insert(
    mapper,
    connection,
    target,
) -> None:
    _adr020_require_sha256(target.subject_hash, "subject_hash")
    _adr020_require_sha256(target.record_hash, "record_hash")

    if target.subject_version is None or target.subject_version <= 0:
        raise ValueError(
            "ADR-020 RuleReviewRecord subject_version must be positive"
        )

    if not str(target.subject_id or "").strip():
        raise ValueError(
            "ADR-020 RuleReviewRecord subject_id cannot be empty"
        )

    if not str(target.reviewer or "").strip():
        raise ValueError(
            "ADR-020 RuleReviewRecord reviewer cannot be empty"
        )

    permitted_outcomes = _RULE_REVIEW_EVENT_OUTCOMES.get(
        target.review_event
    )
    if (
        permitted_outcomes is None
        or target.outcome not in permitted_outcomes
    ):
        raise ValueError(
            "ADR-020 RuleReviewRecord event/outcome pair is invalid"
        )

    if target.evidence is None:
        raise ValueError(
            "ADR-020 RuleReviewRecord requires evidence"
        )



def _adr020_validate_normative_relation_version_insert(
    mapper,
    connection,
    target,
) -> None:
    _adr020_require_sha256(
        target.normative_relation_hash,
        "normative_relation_hash",
    )
    _adr020_require_sha256(
        target.source_subject_hash,
        "source_subject_hash",
    )
    _adr020_require_sha256(
        target.target_subject_hash,
        "target_subject_hash",
    )
    _adr020_require_sha256(
        target.record_hash,
        "record_hash",
    )

    if (
        target.normative_relation_version is None
        or target.normative_relation_version <= 0
    ):
        raise ValueError(
            "ADR-020 NormativeRelationVersion "
            "version must be positive"
        )

    for field_name in (
        "normative_relation_id",
        "source_subject_type",
        "source_subject_id",
        "target_subject_type",
        "target_subject_id",
    ):
        if not str(getattr(target, field_name, "") or "").strip():
            raise ValueError(
                "ADR-020 NormativeRelationVersion "
                f"{field_name} cannot be empty"
            )

    if (
        target.source_subject_version is None
        or target.source_subject_version <= 0
    ):
        raise ValueError(
            "ADR-020 source_subject_version must be positive"
        )

    if (
        target.target_subject_version is None
        or target.target_subject_version <= 0
    ):
        raise ValueError(
            "ADR-020 target_subject_version must be positive"
        )

    if target.relation_type not in _NORMATIVE_RELATION_TYPES:
        raise ValueError(
            "ADR-020 invalid normative relation type"
        )

    if not target.structured_content:
        raise ValueError(
            "ADR-020 NormativeRelationVersion requires "
            "structured_content"
        )

    if target.declared_material_validity is None:
        raise ValueError(
            "ADR-020 NormativeRelationVersion requires "
            "declared material validity"
        )

    if target.exact_precedence_policy_reference is None:
        raise ValueError(
            "ADR-020 NormativeRelationVersion requires "
            "exact precedence policy reference"
        )

    if target.evidence is None:
        raise ValueError(
            "ADR-020 NormativeRelationVersion requires evidence"
        )

    if target.normative_references is None:
        raise ValueError(
            "ADR-020 NormativeRelationVersion requires "
            "normative references"
        )

    if target.provenance is None:
        raise ValueError(
            "ADR-020 NormativeRelationVersion requires provenance"
        )


def _adr020_validate_relation_review_insert(
    mapper,
    connection,
    target,
) -> None:
    _adr020_require_sha256(
        target.subject_hash,
        "subject_hash",
    )
    _adr020_require_sha256(
        target.record_hash,
        "record_hash",
    )

    if (
        target.subject_version is None
        or target.subject_version <= 0
    ):
        raise ValueError(
            "ADR-020 RelationReviewRecord "
            "subject_version must be positive"
        )

    if not str(target.subject_id or "").strip():
        raise ValueError(
            "ADR-020 RelationReviewRecord "
            "subject_id cannot be empty"
        )

    if not str(target.reviewer or "").strip():
        raise ValueError(
            "ADR-020 RelationReviewRecord "
            "reviewer cannot be empty"
        )

    permitted_outcomes = (
        _RULE_REVIEW_EVENT_OUTCOMES.get(
            target.review_event
        )
    )
    if (
        permitted_outcomes is None
        or target.outcome not in permitted_outcomes
    ):
        raise ValueError(
            "ADR-020 RelationReviewRecord "
            "event/outcome pair is invalid"
        )

    if target.evidence is None:
        raise ValueError(
            "ADR-020 RelationReviewRecord requires evidence"
        )


_POLICY_TYPES = {
    "activation_authority",
    "automation_envelope",
    "normative_precedence",
    "normative_continuity",
    "coverage_contract",
}
_POLICY_DECISION_ROLES = {
    "submetida": "proponente_institucional",
    "auditoria_iniciada": "auditor_independente",
    "auditada_favoravelmente": "auditor_independente",
    "auditada_desfavoravelmente": "auditor_independente",
    "ratificada": "autoridade_constitucional_final",
    "rejeitada": "autoridade_institucional_competente",
    "cancelada": "autoridade_institucional_competente",
}
_POLICY_TERMINAL_DECISIONS = {
    "auditada_desfavoravelmente",
    "ratificada",
    "rejeitada",
    "cancelada",
}


def _adr020_validate_policy_version_insert(mapper, connection, target) -> None:
    _adr020_require_sha256(target.policy_hash, "policy_hash")
    _adr020_require_sha256(target.record_hash, "record_hash")
    if target.policy_type not in _POLICY_TYPES:
        raise ValueError("ADR-020 invalid policy_type")
    if target.policy_version is None or target.policy_version <= 0:
        raise ValueError("ADR-020 PolicyVersion version must be positive")
    for field_name in ("policy_id", "domain"):
        if not str(getattr(target, field_name, "") or "").strip():
            raise ValueError(f"ADR-020 PolicyVersion {field_name} cannot be empty")
    for field_name in (
        "scope", "declared_material_applicability", "modalities",
        "permitted_authorization_classes", "permitted_execution_modes",
        "gates", "roles", "segregation_of_duties", "limits", "rules",
        "exact_references", "origin_evidence",
    ):
        if getattr(target, field_name, None) is None:
            raise ValueError(f"ADR-020 PolicyVersion requires {field_name}")


def _adr020_validate_policy_decision_insert(mapper, connection, target) -> None:
    _adr020_require_sha256(target.policy_hash, "policy_hash")
    _adr020_require_sha256(target.record_hash, "record_hash")
    if target.policy_type not in _POLICY_TYPES:
        raise ValueError("ADR-020 invalid policy_type")
    expected_role = _POLICY_DECISION_ROLES.get(target.decision_event)
    if expected_role is None or target.institutional_role != expected_role:
        raise ValueError("ADR-020 invalid decision event/institutional role")
    if target.policy_version is None or target.policy_version <= 0:
        raise ValueError("ADR-020 PolicyDecision version must be positive")
    for field_name in ("decision_id", "policy_id", "actor", "rationale", "idempotency_key"):
        if not str(getattr(target, field_name, "") or "").strip():
            raise ValueError(f"ADR-020 PolicyDecision {field_name} cannot be empty")
    if target.evidence is None:
        raise ValueError("ADR-020 PolicyDecision requires evidence")
    if target.decision_event == "submetida":
        if target.previous_decision_id is not None:
            raise ValueError("ADR-020 submission cannot have a predecessor")
    elif target.previous_decision_id is None:
        raise ValueError("ADR-020 institutional decision requires predecessor audit chain")
    previous_event = getattr(target, "previous_decision_event", None)
    if previous_event in _POLICY_TERMINAL_DECISIONS:
        raise ValueError("ADR-020 terminal PolicyDecision cannot be reopened")
    if target.decision_event == "ratificada" and previous_event not in (
        None,
        "auditada_favoravelmente",
    ):
        raise ValueError("ADR-020 ratification requires favorable independent audit")


def _adr020_validate_bootstrap_authority_insert(mapper, connection, target) -> None:
    _adr020_require_sha256(target.policy_hash, "policy_hash")
    _adr020_require_sha256(target.record_hash, "record_hash")
    if target.policy_type != "activation_authority":
        raise ValueError("ADR-020 bootstrap is exclusively activation_authority")
    if target.independent_audit_result != "favoravel":
        raise ValueError("ADR-020 bootstrap requires favorable independent audit")
    if target.validity != "valida":
        raise ValueError("ADR-020 bootstrap authority must be valid")
    modes = (
        target.submission_mode,
        target.audit_mode,
        target.ratification_mode,
        target.activation_mode,
    )
    if any(mode != "manual" for mode in modes):
        raise ValueError("ADR-020 bootstrap is exclusively constitutional and manual")
    actors = (target.actor_proponente, target.actor_auditor, target.actor_ratificador)
    if any(not str(actor or "").strip() for actor in actors) or len(set(actors)) != 3:
        raise ValueError("ADR-020 bootstrap requires institutional segregation")
    if not str(target.constitutional_authority_declaration or "").strip():
        raise ValueError("ADR-020 bootstrap requires express constitutional declaration")
    for field_name in ("scope", "segregation_evidence", "evidence", "provenance"):
        if getattr(target, field_name, None) is None:
            raise ValueError(f"ADR-020 bootstrap requires {field_name}")


def _adr020_validate_coverage_contract_insert(mapper, connection, target) -> None:
    _adr020_require_sha256(target.contract_hash, "contract_hash")
    _adr020_require_sha256(target.record_hash, "record_hash")
    if target.contract_version is None or target.contract_version <= 0:
        raise ValueError("ADR-020 CoverageContract version must be positive")
    if target.contract_state not in {"proposta", "auditada", "ratificada", "revogada"}:
        raise ValueError("ADR-020 invalid CoverageContract state")
    for field_name in ("coverage_contract_id", "source_id", "timezone", "adapter_id"):
        if not str(getattr(target, field_name, "") or "").strip():
            raise ValueError(f"ADR-020 CoverageContract {field_name} cannot be empty")
    if target.effective_to is not None and target.effective_to <= target.effective_from:
        raise ValueError("ADR-020 CoverageContract validity is not ordered")
    for field_name in (
        "expected_calendar", "publication_schedule", "delay_windows",
        "mandatory_sections", "expected_files_partitions", "pagination",
        "cursors", "empty_response_semantics", "proven_absence_rules",
        "authorized_redirects", "media_types", "compatible_adapter_versions",
        "technical_limits", "retry_policy", "continuity_policy_reference",
        "evidence", "audit", "ratification", "revocation",
    ):
        if getattr(target, field_name, None) is None:
            raise ValueError(f"ADR-020 CoverageContract requires {field_name}")


def _adr020_validate_coverage_ledger_insert(mapper, connection, target) -> None:
    _adr020_require_sha256(target.contract_hash, "contract_hash")
    _adr020_require_sha256(target.record_hash, "record_hash")
    if target.contract_version is None or target.contract_version <= 0:
        raise ValueError("ADR-020 ledger contract version must be positive")
    if target.unit_order is None or target.unit_order <= 0:
        raise ValueError("ADR-020 ledger unit order must be positive")
    if target.fencing_token is None or target.fencing_token <= 0:
        raise ValueError("ADR-020 ledger fencing token must be positive")
    if target.window_end <= target.window_start:
        raise ValueError("ADR-020 ledger window is not ordered")
    if target.unit_type not in {"publication", "section", "page", "file", "partition", "period"}:
        raise ValueError("ADR-020 invalid ledger unit type")
    if target.observation_outcome not in {"observed", "not_observed", "source_unavailable"}:
        raise ValueError("ADR-020 invalid ledger observation outcome")
    if target.processing_outcome not in {"pending", "succeeded", "failed", "proven_absence"}:
        raise ValueError("ADR-020 invalid ledger processing outcome")
    if target.coverage_outcome not in {"covered", "gap", "not_covered"}:
        raise ValueError("ADR-020 invalid ledger coverage outcome")
    if target.response_kind not in {"non_empty", "empty", "not_applicable"}:
        raise ValueError("ADR-020 invalid ledger response kind")
    if target.coverage_outcome == "covered" and target.processing_outcome not in {"succeeded", "proven_absence"}:
        raise ValueError("ADR-020 failure or pending result cannot be promoted to coverage")
    if target.response_kind == "empty" and target.coverage_outcome == "covered" and not target.cycle_fully_evaluated:
        raise ValueError("ADR-020 empty response requires an integral completed cycle")
    for field_name in ("coverage_ledger_entry_id", "coverage_contract_id", "unit_id"):
        if not str(getattr(target, field_name, "") or "").strip():
            raise ValueError(f"ADR-020 ledger {field_name} cannot be empty")
    if target.evidence is None or target.provenance is None:
        raise ValueError("ADR-020 ledger requires evidence and provenance")


def _adr020_validate_coverage_checkpoint_insert(mapper, connection, target) -> None:
    _adr020_require_sha256(target.contract_hash, "contract_hash")
    _adr020_require_sha256(target.record_hash, "record_hash")
    if target.contract_version is None or target.contract_version <= 0:
        raise ValueError("ADR-020 checkpoint contract version must be positive")
    if target.checkpoint_sequence is None or target.checkpoint_sequence <= 0:
        raise ValueError("ADR-020 checkpoint sequence must be positive")
    if target.fencing_token is None or target.fencing_token <= 0:
        raise ValueError("ADR-020 checkpoint fencing token must be positive")
    if target.window_end <= target.window_start:
        raise ValueError("ADR-020 checkpoint window is not ordered")
    markers = (target.observed_through, target.completed_through, target.covered_through, target.pending_gap_from)
    if any(value is not None and value <= 0 for value in markers):
        raise ValueError("ADR-020 checkpoint markers must be positive")
    if target.completed_through is not None and (target.observed_through is None or target.completed_through > target.observed_through):
        raise ValueError("ADR-020 completed frontier exceeds observed frontier")
    if target.covered_through is not None and (target.completed_through is None or target.covered_through > target.completed_through):
        raise ValueError("ADR-020 covered frontier exceeds completed frontier")
    expected_gap = (target.covered_through or 0) + 1
    if target.pending_gap_from is not None and target.pending_gap_from != expected_gap:
        raise ValueError("ADR-020 checkpoint must preserve the first contiguous gap")
    if target.pending_gap_from is None and not target.cycle_fully_evaluated:
        raise ValueError("ADR-020 no pending gap requires an integral evaluated cycle")
    for field_name in ("coverage_checkpoint_record_id", "coverage_contract_id", "last_ledger_entry_id"):
        if not str(getattr(target, field_name, "") or "").strip():
            raise ValueError(f"ADR-020 checkpoint {field_name} cannot be empty")
    if target.evidence is None or target.provenance is None:
        raise ValueError("ADR-020 checkpoint requires evidence and provenance")


def _adr020_reject_append_only_mutation(mapper, connection, target) -> None:
    raise RuntimeError(
        "ADR-020 append-only violation: update/delete is forbidden for "
        f"{target.__class__.__name__}"
    )


def _adr020_require_exact_bindings(target) -> None:
    for field_name in ("authority_bindings", "policy_bindings", "coverage_binding", "continuity_binding", "precedence_binding", "gates_evidence"):
        value = getattr(target, field_name, None)
        if value is None:
            raise ValueError(f"ADR-020 requires exact {field_name}")
        if any(word in str(value).lower() for word in ("current", "latest", "newest", "corrente", "mais_recente")):
            raise ValueError("ADR-020 floating reference is forbidden")


def _adr020_validate_policy_activation_execution_insert(mapper, connection, target) -> None:
    _adr020_require_sha256(target.policy_hash, "policy_hash"); _adr020_require_sha256(target.record_hash, "record_hash")
    if target.state not in {"pendente", "em_execucao", "concluida", "falhada", "cancelada"}: raise ValueError("ADR-020 invalid policy activation execution state")
    if target.attempt_number <= 0 or target.fencing_token <= 0: raise ValueError("ADR-020 retry requires a new positive attempt")
    if target.authorization_basis_type == "bootstrap_authority_record":
        if not target.bootstrap_authority_record_id or not target.bootstrap_authority_record_hash: raise ValueError("ADR-020 exact bootstrap authority required")
        _adr020_require_sha256(target.bootstrap_authority_record_hash, "bootstrap_authority_record_hash")
    elif target.authorization_basis_type == "active_policy_chain":
        for name in ("activation_authority_policy_id", "activation_authority_policy_version", "activation_authority_policy_hash", "activation_authority_policy_activation_id"):
            if getattr(target, name, None) in (None, ""): raise ValueError("ADR-020 delegated activation requires exact active superior PolicyActivation")
        _adr020_require_sha256(target.activation_authority_policy_hash, "activation_authority_policy_hash")
    else: raise ValueError("ADR-020 invalid authorization basis")
    if target.execution_mode == "automatico":
        for name in ("automation_envelope_id", "automation_envelope_version", "automation_envelope_hash", "automation_envelope_activation_id"):
            if getattr(target, name, None) in (None, ""): raise ValueError("ADR-020 automatic activation requires exact active automation_envelope")
        _adr020_require_sha256(target.automation_envelope_hash, "automation_envelope_hash")
    if target.state in {"concluida", "falhada", "cancelada"} and target.finished_at is None: raise ValueError("ADR-020 terminal execution requires finished_at")
    if target.state == "concluida" and target.structured_result is None: raise ValueError("ADR-020 completed execution requires atomic result")


def _adr020_validate_policy_activation_insert(mapper, connection, target) -> None:
    _adr020_require_sha256(target.policy_hash, "policy_hash"); _adr020_require_sha256(target.record_hash, "record_hash")
    if target.state not in {"activa", "suspensa", "desactivada", "expirada", "revogada"}: raise ValueError("ADR-020 invalid PolicyActivation state")


def _adr020_validate_activation_decision_insert(mapper, connection, target) -> None:
    from app.schemas.adr020_bindings import ADR020BindingsContract

    try:
        ADR020BindingsContract(
            authority_bindings=target.authority_bindings,
            policy_bindings=target.policy_bindings,
            coverage_binding=target.coverage_binding,
            continuity_binding=target.continuity_binding,
            precedence_binding=target.precedence_binding,
            gates_evidence=target.gates_evidence,
        )
    except ValueError as exc:
        raise ValueError(
            "activation decision bindings must satisfy ADR020BindingsContract"
        ) from exc
    for name in ("scope_hash", "target_manifest_hash", "record_hash"): _adr020_require_sha256(getattr(target, name), name)
    if target.decision_outcome not in {"approved", "rejected", "cancelled"}: raise ValueError("ADR-020 invalid activation decision outcome")
    if target.decision_action == "activate":
        if not target.target_manifest or any(item.get("review_outcome") != "validada" for item in target.target_manifest): raise ValueError("ADR-020 activation requires favorable exact review")


def _adr020_validate_activation_execution_insert(mapper, connection, target) -> None:
    for name in ("activation_decision_record_hash", "scope_hash", "target_manifest_hash", "record_hash"): _adr020_require_sha256(getattr(target, name), name)
    if target.decision_outcome != "approved": raise ValueError("ADR-020 rejected or cancelled decision cannot be executed")
    if target.authorization_class == "constitucional_reservada" and target.execution_mode != "manual": raise ValueError("ADR-020 reserved activation is manual")
    if target.execution_mode == "automatico" and target.authorization_class != "automatica_delegada": raise ValueError("ADR-020 automatic execution requires delegated automation")
    if target.attempt_number <= 0 or target.fencing_token <= 0: raise ValueError("ADR-020 retry requires new execution attempt")
    from app.schemas.adr020_bindings import ADR020BindingsContract

    try:
        ADR020BindingsContract.model_validate(
            {
                "authority_bindings": target.authority_bindings,
                "policy_bindings": target.policy_bindings,
                "coverage_binding": target.coverage_binding,
                "continuity_binding": target.continuity_binding,
                "precedence_binding": target.precedence_binding,
                "gates_evidence": target.gates_evidence,
            },
            strict=True,
        )
    except ValueError as exc:
        raise ValueError(
            "activation execution bindings must satisfy ADR020BindingsContract"
        ) from exc
    if target.state in {"completed", "failed", "cancelled"} and target.finished_at is None: raise ValueError("ADR-020 terminal execution requires finished_at")
    if target.state == "completed" and target.structured_result is None: raise ValueError("ADR-020 completed execution requires atomic result")


def _adr020_validate_normative_activation_insert(mapper, connection, target) -> None:
    for name in ("activation_decision_record_hash", "subject_hash", "review_record_hash", "scope_hash", "record_hash"): _adr020_require_sha256(getattr(target, name), name)
    if target.state not in {"active", "suspended", "deactivated", "expired", "revoked"}: raise ValueError("ADR-020 invalid NormativeActivation state")


def _adr020_validate_activation_generation_insert(mapper, connection, target) -> None:
    for name in ("activation_decision_record_hash", "target_manifest_hash", "scope_hash", "composition_hash", "record_hash"): _adr020_require_sha256(getattr(target, name), name)
    if not target.is_complete or not isinstance(target.composition_manifest, list): raise ValueError("ADR-020 partial generation is forbidden")
    if (target.previous_activation_generation_id is None) != (target.previous_activation_generation_record_hash is None): raise ValueError("ADR-020 previous generation identity and hash must be exact")
    _adr020_require_exact_bindings(target)


def _adr020_validate_outbox_event_insert(mapper, connection, target) -> None:
    for name in ("scope_hash", "composition_hash", "payload_hash", "record_hash"): _adr020_require_sha256(getattr(target, name), name)
    if target.event_type not in {"activation_completed", "activation_invalidated"}: raise ValueError("ADR-020 invalid outbox event type")


_ADR020_SENSITIVE_TERMS = ("authorization", "proxy-authorization", "cookie", "set-cookie", "api_key", "apikey", "token", "password", "client_secret", "private_key", "secret_hash", "secret_value")


def _adr020_reject_sensitive_material(value, field_name) -> None:
    text = str(value or "").lower()
    if any(term in text for term in _ADR020_SENSITIVE_TERMS):
        raise ValueError(f"ADR-020 sensitive material is forbidden in {field_name}")


def _adr020_validate_binding_insert(mapper, connection, target) -> None:
    for name in ("credential_binding_hash", "record_hash"): _adr020_require_sha256(getattr(target, name), name)
    if target.credential_binding_version <= 0 or (target.valid_until is not None and target.valid_until <= target.valid_from): raise ValueError("ADR-020 invalid credential binding version or validity")
    provider = target.secret_provider_binding
    required = {"secret_provider_id", "secret_provider_version", "secret_provider_artifact_hash", "provider_interface_contract_id", "provider_interface_contract_version", "provider_interface_contract_hash"}
    if not isinstance(provider, dict) or not required.issubset(provider): raise ValueError("ADR-020 exact provider binding is required")
    for binding_name in ("secret_access_policy_binding", "security_policy_binding", "sanitization_policy_binding"):
        binding = getattr(target, binding_name)
        if not isinstance(binding, dict) or not {"policy_type", "policy_id", "policy_version", "policy_hash", "policy_activation_id", "policy_activation_record_hash"}.issubset(binding): raise ValueError("ADR-020 exact active policy binding is required")
    for name in ("secret_provider_binding", "opaque_secret_reference_id", "opaque_secret_version_reference_id", "provenance"): _adr020_reject_sensitive_material(getattr(target, name), name)
    _adr020_require_exact_bindings(target)


def _adr020_validate_lifecycle_insert(mapper, connection, target) -> None:
    for name in ("credential_binding_hash", "record_hash"): _adr020_require_sha256(getattr(target, name), name)
    first = target.previous_lifecycle_event_record_id is None
    if first != (target.lifecycle_event == "activated"): raise ValueError("ADR-020 lifecycle must begin with activated and remain contiguous")
    if first != (target.previous_lifecycle_event_record_hash is None): raise ValueError("ADR-020 lifecycle predecessor ID/hash must be exact")
    previous = getattr(target, "previous_lifecycle_event", None)
    if previous in {"revoked", "expired", "rotated"}: raise ValueError("ADR-020 terminal lifecycle event cannot be reopened")
    if target.lifecycle_event == "resumed" and previous not in (None, "suspended"): raise ValueError("ADR-020 only suspended binding may resume")
    replacement = (target.replacement_credential_binding_id, target.replacement_credential_binding_version, target.replacement_credential_binding_hash)
    if (target.lifecycle_event == "rotated") != all(item is not None for item in replacement): raise ValueError("ADR-020 rotation requires an exact replacement binding")


def _adr020_validate_secret_access_insert(mapper, connection, target) -> None:
    for name in ("acquisition_execution_record_hash", "credential_binding_hash", "credential_lifecycle_event_record_hash", "secret_provider_artifact_hash", "lease_record_hash", "record_hash"): _adr020_require_sha256(getattr(target, name), name)
    if target.attempt_number <= 0 or target.fencing_token <= 0 or not target.lease_id: raise ValueError("ADR-020 access requires new attempt, lease and fence")
    if target.access_state in {"authorized", "accessed"} and getattr(target, "binding_lifecycle_state", "activated") != "activated": raise ValueError("ADR-020 inactive binding cannot authorize access")
    for name in ("structured_result", "structured_error", "provenance"): _adr020_reject_sensitive_material(getattr(target, name), name)


def _adr020_validate_credential_use_insert(mapper, connection, target) -> None:
    for name in ("acquisition_execution_record_hash", "secret_access_execution_record_hash", "credential_binding_hash", "credential_lifecycle_event_record_hash", "request_contract_hash", "sanitized_request_fingerprint", "sanitized_request_canonicalization_contract_hash", "record_hash"): _adr020_require_sha256(getattr(target, name), name)
    if getattr(target, "secret_access_state", "accessed") not in {"authorized", "accessed"}: raise ValueError("ADR-020 credential use requires favorable terminal access")
    if target.previous_credential_use_record_id is None != (target.previous_credential_use_record_hash is None): raise ValueError("ADR-020 use predecessor ID/hash must be exact")
    for name in ("structured_result", "structured_error", "provenance"): _adr020_reject_sensitive_material(getattr(target, name), name)


def _adr020_validate_receipt_insert(mapper, connection, target) -> None:
    for name in ("sanitized_acquisition_receipt_hash", "acquisition_execution_record_hash", "credential_use_record_hash", "credential_binding_hash", "request_contract_hash", "sanitized_request_fingerprint", "sanitized_request_canonicalization_contract_hash", "record_hash"): _adr020_require_sha256(getattr(target, name), name)
    if target.acquired_content_hash is not None: _adr020_require_sha256(target.acquired_content_hash, "acquired_content_hash")
    allowed_request = {"method", "source_identity", "path", "parameter_names", "parameter_types", "sanitized_payload_hash", "request_contract_version"}
    if not isinstance(target.sanitized_request_manifest, dict) or not set(target.sanitized_request_manifest).issubset(allowed_request): raise ValueError("ADR-020 request manifest contains a non-allowlisted field")
    allowed_redaction = {"component_type", "canonical_location", "sensitivity_category", "sanitization_action", "policy_rule_id", "policy_rule_version", "policy_rule_hash", "verification_outcome"}
    if not isinstance(target.redaction_manifest, list) or any(not isinstance(item, dict) or set(item) != allowed_redaction for item in target.redaction_manifest): raise ValueError("ADR-020 redaction manifest must be exact")
    for name in ("sanitized_request_manifest", "sanitized_response_metadata", "transport_evidence_manifest", "redaction_manifest", "provenance"): _adr020_reject_sensitive_material(getattr(target, name), name)


def _adr020_validate_sanitization_verification_insert(mapper, connection, target) -> None:
    for name in ("sanitized_acquisition_receipt_hash", "sanitization_policy_hash", "sanitization_policy_activation_record_hash", "verification_engine_hash", "record_hash"): _adr020_require_sha256(getattr(target, name), name)
    if target.verification_outcome == "verified_sanitized":
        if not isinstance(target.inspected_component_manifest, dict) or target.inspected_component_manifest.get("complete") is not True or target.violation_manifest not in ([], {}): raise ValueError("ADR-020 partial or violated verification cannot be approved")
    _adr020_reject_sensitive_material(target.violation_manifest, "violation_manifest")


def _adr020_exact_pair(target, identity_name, hash_name, label) -> None:
    identity = getattr(target, identity_name, None)
    digest = getattr(target, hash_name, None)
    if (identity is None) != (digest is None):
        raise ValueError(f"ADR-020 {label} ID/hash must be exact")
    if digest is not None:
        _adr020_require_sha256(digest, hash_name)


def _adr020_validate_generation_fence_insert(mapper, connection, target) -> None:
    for name in ("scope_hash", "activation_generation_record_hash", "activation_execution_record_hash", "publisher_lease_record_hash", "composition_hash", "source_event_record_hash", "record_hash"):
        _adr020_require_sha256(getattr(target, name), name)
    _adr020_exact_pair(target, "previous_generation_fence_record_id", "previous_generation_fence_record_hash", "fence predecessor")
    if target.generation_sequence <= 0 or target.fencing_token <= 0:
        raise ValueError("ADR-020 fence sequence and fencing token must be positive")
    previous_sequence = getattr(target, "previous_generation_sequence", None)
    previous_token = getattr(target, "previous_fencing_token", None)
    first = target.previous_generation_fence_record_id is None
    if first and target.generation_sequence != 1:
        raise ValueError("ADR-020 first fence sequence must be exactly 1")
    if not first and previous_sequence is not None and target.generation_sequence != previous_sequence + 1:
        raise ValueError("ADR-020 fence sequence must be contiguous")
    if not first and previous_token is not None and target.fencing_token <= previous_token:
        raise ValueError("ADR-020 stale or divergent fencing token")
    if getattr(target, "activation_generation_is_complete", True) is not True:
        raise ValueError("ADR-020 incomplete generation cannot be fenced")
    if getattr(target, "activation_execution_state", "completed") != "completed":
        raise ValueError("ADR-020 fence requires completed activation execution")
    for own, exact in (("scope_hash", "activation_generation_scope_hash"), ("composition_hash", "activation_generation_composition_hash"), ("activation_execution_id", "activation_generation_execution_id")):
        expected = getattr(target, exact, getattr(target, own))
        if getattr(target, own) != expected:
            raise ValueError("ADR-020 fence and generation binding diverge")


def _adr020_validate_consumer_contract_insert(mapper, connection, target) -> None:
    for name in ("consumer_contract_hash", "allowed_scope_hash", "record_hash"):
        _adr020_require_sha256(getattr(target, name), name)
    if target.consumer_contract_version <= 0 or target.supported_protocol_version <= 0 or target.supported_generation_schema_version <= 0:
        raise ValueError("ADR-020 consumer contract versions must be positive")
    if target.consumer_type not in {"service", "replica", "batch", "interactive"}:
        raise ValueError("ADR-020 invalid consumer type")
    for name in ("allowed_scope_descriptor", "compatibility_rules", "freshness_policy_binding", "security_policy_binding", "provenance"):
        value = getattr(target, name, None)
        if value is None:
            raise ValueError(f"ADR-020 consumer contract requires {name}")
        if any(word in str(value).lower() for word in ("current", "latest", "newest", "corrente", "mais_recente")):
            raise ValueError("ADR-020 floating consumer contract reference is forbidden")
    required_policy = {"policy_type", "policy_id", "policy_version", "policy_hash", "policy_activation_id", "policy_activation_record_hash"}
    for name in ("freshness_policy_binding", "security_policy_binding"):
        if not isinstance(getattr(target, name), dict) or not required_policy.issubset(getattr(target, name)):
            raise ValueError("ADR-020 exact active consumer policy binding is required")


def _adr020_validate_consumer_application_insert(mapper, connection, target) -> None:
    for name in ("consumer_contract_hash", "scope_hash", "generation_fence_record_hash", "activation_generation_record_hash", "composition_hash", "record_hash"):
        _adr020_require_sha256(getattr(target, name), name)
    for identity, digest, label in (("previous_replica_checkpoint_record_id", "previous_replica_checkpoint_record_hash", "checkpoint predecessor"), ("duplicate_of_consumer_application_record_id", "duplicate_of_consumer_application_record_hash", "duplicate application"), ("duplicate_of_replica_checkpoint_record_id", "duplicate_of_replica_checkpoint_record_hash", "duplicate checkpoint")):
        _adr020_exact_pair(target, identity, digest, label)
    if target.attempt_number <= 0 or target.generation_sequence <= 0 or target.fencing_token <= 0:
        raise ValueError("ADR-020 application attempt, sequence and fence must be positive")
    terminal = {"applied", "duplicate_exact", "rejected_stale", "rejected_gap", "rejected_divergent", "rejected_incompatible", "failed", "cancelled"}
    if target.application_result in terminal and target.finished_at is None:
        raise ValueError("ADR-020 terminal application requires finished_at")
    duplicate_fields = (target.duplicate_of_consumer_application_record_id, target.duplicate_of_replica_checkpoint_record_id)
    if (target.application_result == "duplicate_exact") != all(value is not None for value in duplicate_fields):
        raise ValueError("ADR-020 duplicate_exact requires exact prior application and checkpoint")
    if target.application_result == "applied":
        if not isinstance(target.structured_result, dict) or target.structured_result.get("application_complete") is not True:
            raise ValueError("ADR-020 partial application is forbidden")
    for own, exact in (("scope_hash", "contract_allowed_scope_hash"), ("scope_hash", "fence_scope_hash"), ("generation_sequence", "fence_generation_sequence"), ("fencing_token", "fence_fencing_token"), ("activation_generation_id", "fence_activation_generation_id"), ("activation_generation_record_hash", "fence_activation_generation_record_hash"), ("composition_hash", "fence_composition_hash")):
        expected = getattr(target, exact, getattr(target, own))
        if getattr(target, own) != expected:
            raise ValueError("ADR-020 incompatible contract, fence or generation")


def _adr020_validate_replica_checkpoint_insert(mapper, connection, target) -> None:
    for name in ("consumer_application_record_hash", "consumer_contract_hash", "scope_hash", "generation_fence_record_hash", "activation_generation_record_hash", "composition_hash", "record_hash"):
        _adr020_require_sha256(getattr(target, name), name)
    _adr020_exact_pair(target, "previous_replica_checkpoint_record_id", "previous_replica_checkpoint_record_hash", "replica checkpoint predecessor")
    if target.generation_sequence <= 0 or target.fencing_token <= 0:
        raise ValueError("ADR-020 replica checkpoint sequence and fence must be positive")
    if getattr(target, "consumer_application_result", "applied") != "applied" or getattr(target, "consumer_application_complete", True) is not True:
        raise ValueError("ADR-020 checkpoint requires an exact integral applied application")
    previous_sequence = getattr(target, "previous_generation_sequence", None)
    first = target.previous_replica_checkpoint_record_id is None
    if first and target.generation_sequence != 1:
        raise ValueError("ADR-020 first replica checkpoint must be explicitly sequence 1")
    if not first and previous_sequence is not None and target.generation_sequence != previous_sequence + 1:
        raise ValueError("ADR-020 replica checkpoint sequence must be contiguous")
    for own, exact in (("consumer_id", "application_consumer_id"), ("replica_id", "application_replica_id"), ("replica_instance_id", "application_replica_instance_id"), ("consumer_contract_version", "application_consumer_contract_version"), ("consumer_contract_hash", "application_consumer_contract_hash"), ("scope_hash", "application_scope_hash"), ("generation_fence_record_id", "application_generation_fence_record_id"), ("generation_fence_record_hash", "application_generation_fence_record_hash"), ("generation_sequence", "application_generation_sequence"), ("fencing_token", "application_fencing_token"), ("activation_generation_id", "application_activation_generation_id"), ("activation_generation_record_hash", "application_activation_generation_record_hash"), ("composition_hash", "application_composition_hash")):
        expected = getattr(target, exact, getattr(target, own))
        if getattr(target, own) != expected:
            raise ValueError("ADR-020 divergent replica checkpoint is forbidden")


_ADR020_FLOATING_TERMS = ("current", "latest", "newest", "actual", "corrente", "mais_recente", "mais recente")
_ADR020_EXTERNAL_IO_TERMS = ("http" + "://", "https" + "://", "net" + "work", "rede", "socket", "requests" + ".", "htt" + "px")
_ADR020_CLOCK_TERMS = ("now()", "current_timestamp", "datetime.now", "utcnow", "relógio corrente", "relogio corrente")


def _adr020_reject_nondeterministic_material(target, fields) -> None:
    for field_name in fields:
        value = getattr(target, field_name, None)
        text = str(value or "").lower()
        _adr020_reject_sensitive_material(value, field_name)
        if any(term in text for term in _ADR020_FLOATING_TERMS):
            raise ValueError("ADR-020 floating or current state reference is forbidden")
        if any(term in text for term in _ADR020_EXTERNAL_IO_TERMS):
            raise ValueError("ADR-020 external transport use is forbidden")
        if any(term in text for term in _ADR020_CLOCK_TERMS):
            raise ValueError("ADR-020 implicit current clock is forbidden")


def _adr020_validate_calculation_bundle_insert(mapper, connection, target) -> None:
    hash_fields = ("calculation_bundle_hash", "scope_hash", "generation_fence_record_hash", "activation_generation_record_hash", "composition_hash", "consumer_contract_hash", "consumer_application_record_hash", "replica_checkpoint_record_hash", "record_hash")
    for name in hash_fields: _adr020_require_sha256(getattr(target, name), name)
    if target.calculation_bundle_schema_version <= 0 or target.generation_sequence <= 0 or target.fencing_token <= 0: raise ValueError("ADR-020 bundle versions and fences must be positive")
    required = ("calculation_subject_reference", "input_snapshot_manifest", "normative_member_manifest", "policy_binding_manifest", "coverage_binding", "continuity_binding", "precedence_binding", "gates_evidence", "engine_binding", "runtime_binding", "canonical_serialization_binding", "deterministic_seed_binding", "evaluation_instant", "provenance")
    if any(getattr(target, name, None) is None for name in required): raise ValueError("ADR-020 incomplete CalculationBundle is forbidden")
    if not isinstance(target.input_snapshot_manifest, list) or not target.input_snapshot_manifest: raise ValueError("ADR-020 bundle requires integral exact inputs")
    input_keys = {"input_type", "input_id", "input_record_hash", "input_payload_hash", "canonicalization_contract_id", "canonicalization_contract_version", "canonicalization_contract_hash", "immutable_content_reference", "immutable_content_hash"}
    if any(not isinstance(item, dict) or not input_keys.issubset(item) for item in target.input_snapshot_manifest): raise ValueError("ADR-020 incomplete input snapshot is forbidden")
    runtime = target.runtime_binding
    if not isinstance(runtime, dict) or not {"runtime_artifact_id", "runtime_artifact_version", "runtime_artifact_hash", "dependency_manifest", "dependency_manifest_hash", "platform_contract_id", "platform_contract_version", "platform_contract_hash"}.issubset(runtime): raise ValueError("ADR-020 exact runtime and dependencies are required")
    dependencies = runtime.get("dependency_manifest")
    if not isinstance(dependencies, list) or any(not {"dependency_id", "dependency_version", "dependency_hash"}.issubset(item) for item in dependencies): raise ValueError("ADR-020 floating dependency is forbidden")
    _adr020_reject_nondeterministic_material(target, required)
    exact = (("scope_hash", "fence_scope_hash"), ("generation_sequence", "fence_generation_sequence"), ("fencing_token", "fence_fencing_token"), ("activation_generation_id", "fence_activation_generation_id"), ("activation_generation_record_hash", "fence_activation_generation_record_hash"), ("composition_hash", "fence_composition_hash"), ("consumer_contract_hash", "application_consumer_contract_hash"), ("consumer_application_record_id", "checkpoint_consumer_application_record_id"), ("replica_checkpoint_record_id", "exact_replica_checkpoint_record_id"))
    for own, reference in exact:
        if getattr(target, reference, getattr(target, own)) != getattr(target, own): raise ValueError("ADR-020 divergent generation, fence, consumer, application or checkpoint")
    if getattr(target, "activation_generation_is_complete", True) is not True or getattr(target, "consumer_application_result", "applied") != "applied" or getattr(target, "consumer_application_complete", True) is not True: raise ValueError("ADR-020 integral generation and terminal application required")


def _adr020_validate_calculation_execution_insert(mapper, connection, target) -> None:
    for name in ("calculation_bundle_hash", "engine_artifact_hash", "runtime_artifact_hash", "record_hash"): _adr020_require_sha256(getattr(target, name), name)
    if target.attempt_number <= 0 or target.fencing_token <= 0: raise ValueError("ADR-020 retry requires a new positive execution and fence")
    if target.state in {"completed", "rejected_incomplete", "rejected_divergent", "rejected_incompatible", "failed", "cancelled"} and target.finished_at is None: raise ValueError("ADR-020 terminal calculation execution requires finished_at")
    if target.state == "completed" and (not isinstance(target.structured_result, dict) or target.structured_result.get("calculation_complete") is not True): raise ValueError("ADR-020 partial calculation cannot complete")
    if getattr(target, "exact_bundle_hash", target.calculation_bundle_hash) != target.calculation_bundle_hash: raise ValueError("ADR-020 execution requires exact bundle")
    _adr020_reject_nondeterministic_material(target, ("structured_result", "structured_error", "provenance"))


def _adr020_validate_calculation_result_insert(mapper, connection, target) -> None:
    for name in ("calculation_execution_record_hash", "calculation_bundle_hash", "result_payload_hash", "calculation_trace_hash", "decision_trace_hash", "canonical_result_hash", "record_hash"): _adr020_require_sha256(getattr(target, name), name)
    if target.result_schema_version <= 0 or getattr(target, "calculation_execution_state", "completed") != "completed": raise ValueError("ADR-020 result requires completed execution")
    if getattr(target, "calculation_execution_bundle_id", target.calculation_bundle_id) != target.calculation_bundle_id or getattr(target, "calculation_execution_bundle_hash", target.calculation_bundle_hash) != target.calculation_bundle_hash: raise ValueError("ADR-020 result requires exact execution and bundle")
    if getattr(target, "calculation_complete", True) is not True or any(getattr(target, name, None) is None for name in ("result_payload_reference", "calculation_trace_reference", "decision_trace_reference", "provenance")): raise ValueError("ADR-020 partial result is forbidden")
    _adr020_reject_nondeterministic_material(target, ("result_payload_reference", "calculation_trace_reference", "decision_trace_reference", "provenance"))


def _adr020_validate_replay_execution_insert(mapper, connection, target) -> None:
    hashes = ("calculation_bundle_hash", "original_calculation_execution_record_hash", "original_calculation_result_record_hash", "original_canonical_result_hash", "replay_engine_artifact_hash", "replay_runtime_artifact_hash", "replay_dependency_manifest_hash", "replay_platform_contract_hash", "replay_canonical_serialization_contract_hash", "replay_deterministic_seed_binding_hash", "record_hash")
    for name in hashes: _adr020_require_sha256(getattr(target, name), name)
    if target.attempt_number <= 0: raise ValueError("ADR-020 replay retry requires a new execution")
    if target.state in {"completed", "rejected_incomplete", "rejected_divergent", "rejected_incompatible", "failed", "cancelled"} and target.finished_at is None: raise ValueError("ADR-020 terminal replay requires finished_at")
    if target.state == "completed":
        for name in ("replay_result_payload_hash", "replay_calculation_trace_hash", "replay_decision_trace_hash", "replay_canonical_result_hash"): _adr020_require_sha256(getattr(target, name), name)
    for own, original in (("calculation_bundle_hash", "original_bundle_hash"), ("replay_engine_artifact_hash", "original_engine_artifact_hash"), ("replay_runtime_artifact_hash", "original_runtime_artifact_hash"), ("replay_evaluation_instant", "original_evaluation_instant")):
        if getattr(target, original, getattr(target, own)) != getattr(target, own): raise ValueError("ADR-020 replay must use exact original bundle and state")
    _adr020_reject_nondeterministic_material(target, ("structured_result", "structured_error", "provenance"))


def _adr020_validate_replay_verification_insert(mapper, connection, target) -> None:
    for name in ("replay_execution_record_hash", "calculation_bundle_hash", "original_calculation_result_record_hash", "original_canonical_result_hash", "record_hash"): _adr020_require_sha256(getattr(target, name), name)
    if target.replay_canonical_result_hash is not None: _adr020_require_sha256(target.replay_canonical_result_hash, "replay_canonical_result_hash")
    complete_match = target.replay_canonical_result_hash == target.original_canonical_result_hash and target.result_payload_match and target.calculation_trace_match and target.decision_trace_match and target.mismatch_manifest in ([], {})
    if target.verification_outcome == "match" and (getattr(target, "replay_execution_state", "completed") != "completed" or not complete_match): raise ValueError("ADR-020 partial verification cannot be match")
    if target.verification_outcome == "mismatch" and not target.mismatch_manifest: raise ValueError("ADR-020 mismatch must preserve evidence")
    if target.verification_outcome == "inconclusive" and getattr(target, "verification_evidence", target.mismatch_manifest) is None: raise ValueError("ADR-020 inconclusive must preserve evidence")
    _adr020_reject_nondeterministic_material(target, ("mismatch_manifest", "provenance"))


_ADR020_INSERT_VALIDATORS = {
    ArtifactReference: _adr020_validate_artifact_reference_insert,
    AcquisitionExecution: _adr020_validate_acquisition_execution_insert,
    NormativeArtifact: _adr020_validate_normative_artifact_insert,
    ArtifactVerificationRecord: _adr020_validate_verification_insert,
    ExtractionRun: _adr020_validate_extraction_run_insert,
    ExtractionResult: _adr020_validate_extraction_result_insert,
    RuleVersion: _adr020_validate_rule_version_insert,
    RuleReviewRecord: _adr020_validate_rule_review_insert,
    NormativeRelationVersion: (
        _adr020_validate_normative_relation_version_insert
    ),
    RelationReviewRecord: (
        _adr020_validate_relation_review_insert
    ),
    PolicyVersion: _adr020_validate_policy_version_insert,
    PolicyDecision: _adr020_validate_policy_decision_insert,
    BootstrapAuthorityRecord: _adr020_validate_bootstrap_authority_insert,
    CoverageContract: _adr020_validate_coverage_contract_insert,
    CoverageLedgerEntry: _adr020_validate_coverage_ledger_insert,
    CoverageCheckpointRecord: _adr020_validate_coverage_checkpoint_insert,
    PolicyActivationExecution: _adr020_validate_policy_activation_execution_insert,
    PolicyActivation: _adr020_validate_policy_activation_insert,
    ActivationDecision: _adr020_validate_activation_decision_insert,
    ActivationExecution: _adr020_validate_activation_execution_insert,
    NormativeActivation: _adr020_validate_normative_activation_insert,
    ActivationGeneration: _adr020_validate_activation_generation_insert,
    OutboxEventRecord: _adr020_validate_outbox_event_insert,
    CredentialBindingVersion: _adr020_validate_binding_insert,
    CredentialLifecycleEventRecord: _adr020_validate_lifecycle_insert,
    SecretAccessExecutionRecord: _adr020_validate_secret_access_insert,
    CredentialUseRecord: _adr020_validate_credential_use_insert,
    SanitizedAcquisitionReceipt: _adr020_validate_receipt_insert,
    SanitizationVerificationRecord: _adr020_validate_sanitization_verification_insert,
    GenerationFenceRecord: _adr020_validate_generation_fence_insert,
    ConsumerContractVersion: _adr020_validate_consumer_contract_insert,
    ConsumerApplicationRecord: _adr020_validate_consumer_application_insert,
    ReplicaCheckpointRecord: _adr020_validate_replica_checkpoint_insert,
    CalculationBundle: _adr020_validate_calculation_bundle_insert,
    CalculationExecutionRecord: _adr020_validate_calculation_execution_insert,
    CalculationResultRecord: _adr020_validate_calculation_result_insert,
    ReplayExecutionRecord: _adr020_validate_replay_execution_insert,
    ReplayVerificationRecord: _adr020_validate_replay_verification_insert,
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

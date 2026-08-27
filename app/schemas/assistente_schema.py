import unicodedata
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class PerguntaRequest(BaseModel):
    """Schema para perguntas enviadas ao Assistente Fiscal."""

    pergunta: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Pergunta do usuário sobre aspectos fiscais",
    )

    @field_validator("pergunta")
    @classmethod
    def normalizar_pergunta(cls, v: str) -> str:
        v = unicodedata.normalize("NFKC", v)

        # Remover caracteres de controle invisíveis
        v = "".join(ch for ch in v if unicodedata.category(ch)[0] != "C")

        v = v.strip()

        # Bloqueio de padrões maliciosos
        bloqueios = [
            "ignore previous instructions",
            "system prompt",
            "you are chatgpt",
            "```",
            "<script",
            "</script",
            "javascript:",
            "onerror=",
        ]

        texto_upper = v.upper()

        for padrao in bloqueios:
            if padrao.upper() in texto_upper:
                raise ValueError("Conteúdo potencialmente malicioso detectado")

        return v

class AssistenteResponse(BaseModel):
    """Estrutura padrão das respostas do Assistente Fiscal.
    Garante compatibilidade entre frontend, assistente, relatórios e pagamento.

    Campos estendidos (IA, multi-idioma, API pública, SEO estruturado):
    ``payload_estruturado``, ``schema_type`` (ex.: HowTo), ``versao`` do formato."""

    resposta: str
    analysis_type: str | None = None  # mei_tax | tax_planning | tax_recovery
    requires_payment: bool = False
    preview: dict | None = None
    payload_estruturado: dict | None = None
    schema_type: str | None = None
    versao: str | None = None
    bloqueado: bool | None = None
    tipo_bloqueio: str | None = None
    estado_l3: str | None = None
    modo: Literal["estimativa", "decisao_definitiva"] | None = None

    @model_validator(mode="after")
    def exigir_modo_mei_comprovado(self):
        if (
            self.analysis_type == "mei_tax"
            and self.bloqueado is not True
            and self.modo is None
        ):
            raise ValueError("Resposta MEI não bloqueada exige modo comprovado")
        return self

"""
SourceAuthority Schema — contrato do guarda de autoridade de fontes tributárias.
"""

from pydantic import BaseModel
from typing import Literal, Optional


class SourceAuthorityRequest(BaseModel):
    fonte_id: str
    uso_pretendido: Literal[
        "fundamentar_decisao",
        "validar_fato_operacional",
        "apoiar_explicacao_ux",
        "contexto_llm",
    ]


class SourceAuthorityResult(BaseModel):
    permitido: bool
    fonte_id: str
    nome: Optional[str] = None
    tipo: Optional[str] = None
    uso_pretendido: str
    motivo: str
    acao: Optional[str] = None
    pode_fundamentar_decisao: Optional[bool] = None
    pode_validar_fato_operacional: Optional[bool] = None
    pode_ser_usada_por_llm: Optional[bool] = None

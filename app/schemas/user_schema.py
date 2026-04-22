import unicodedata

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, ValidationInfo, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=64)
    nome: str | None = Field(default=None, max_length=100)
    tipo_usuario: Literal["cpf", "mei", "empresa"] = Field(default="mei")
    documento: str | None = Field(default=None, max_length=20)

    @field_validator("documento")
    @classmethod
    def validar_documento(cls, v: str | None, info: ValidationInfo) -> str | None:
        if v is None:
            return v
        digits = "".join(c for c in v if c.isdigit())
        tipo = info.data.get("tipo_usuario")
        if tipo == "cpf" and len(digits) != 11:
            raise ValueError("CPF deve ter 11 dígitos")
        if tipo in ("mei", "empresa") and len(digits) != 14:
            raise ValueError("CNPJ deve ter 14 dígitos")
        return digits

    @field_validator("nome")
    @classmethod
    def normalizar_nome(cls, v: str | None) -> str | None:
        if v is None:
            return None

        v = unicodedata.normalize("NFKC", v)
        v = "".join(ch for ch in v if unicodedata.category(ch)[0] != "C")
        v = v.strip()

        # Bloqueio de padrões perigosos
        bloqueios = [
            "<script",
            "</script",
            "javascript:",
            "onerror=",
            "onload=",
        ]

        texto_upper = v.upper()

        for padrao in bloqueios:
            if padrao.upper() in texto_upper:
                raise ValueError("Nome contém conteúdo inválido")

        return v or None


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    empresa_id: int | None = None
    role: str

    class Config:
        from_attributes = True


class UserSession(BaseModel):
    id: int
    email: EmailStr
    plano_id: int | None = None
    consulta_paga: bool
    role: str

    class Config:
        from_attributes = True

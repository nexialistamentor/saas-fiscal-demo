from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nome: str | None = None


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    empresa_id: int | None = None

    class Config:
        from_attributes = True


class UserSession(BaseModel):
    id: int
    email: EmailStr
    plano_id: int | None = None
    consulta_paga: bool

    class Config:
        from_attributes = True

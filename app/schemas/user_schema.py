from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr

    class Config:
        from_attributes = True


class UserSession(BaseModel):
    id: int
    email: EmailStr
    plano_id: int | None = None
    consulta_paga: bool

    class Config:
        from_attributes = True

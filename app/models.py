from sqlalchemy import Column, Integer, String, ForeignKey
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

    usuarios = relationship("User", back_populates="plano")


# =========================
# USER
# =========================
class User(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    plano_id = Column(Integer, ForeignKey("planos.id"))

    plano = relationship("Plano", back_populates="usuarios")
    empresas = relationship("Empresa", back_populates="owner")


# =========================
# EMPRESA
# =========================
class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, index=True)
    cnpj = Column(String, nullable=True)
    razao_social = Column(String, nullable=True)

    user_id = Column(Integer, ForeignKey("usuarios.id"))

    owner = relationship("User", back_populates="empresas")
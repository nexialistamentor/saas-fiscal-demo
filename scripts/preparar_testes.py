#!/usr/bin/env python3
"""
Prepara ambiente para os testes operacionais:
- Cria planos (incl. Teste com limite_analises=2)
- Cria usuários teste@teste.com e outro@teste.com
- Adiciona coluna limite_analises se não existir

Execute: python scripts/preparar_testes.py

Depois: python scripts/testes_operacionais.py
"""
import os
import sys

# Adiciona raiz do projeto ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.models import Plano, User, Empresa
from app.security import hash_senha


def main():
    db = SessionLocal()
    try:
        # 1. Adicionar coluna limite_analises se não existir (SQLite)
        try:
            from sqlalchemy import text
            db.execute(text("ALTER TABLE planos ADD COLUMN limite_analises INTEGER DEFAULT 100"))
            db.commit()
            print("Coluna limite_analises adicionada.")
        except Exception:
            db.rollback()
            # Coluna pode já existir
            pass

        # 2. Planos
        planos_data = [
            ("Basico", 5, 100),
            ("Pro", 10, 500),
            ("Ilimitado", 999999, 999999),
            ("Teste", 2, 2),
        ]
        for nome, limite_cnpjs, limite_analises in planos_data:
            p = db.query(Plano).filter(Plano.nome == nome).first()
            if not p:
                p = Plano(nome=nome, limite_cnpjs=limite_cnpjs, limite_analises=limite_analises)
                db.add(p)
                print(f"Plano {nome} criado.")
            else:
                try:
                    p.limite_analises = limite_analises
                    db.commit()
                    print(f"Plano {nome} atualizado (limite_analises={limite_analises}).")
                except Exception:
                    db.rollback()

        db.commit()
        plano_teste = db.query(Plano).filter(Plano.nome == "Teste").first()
        plano_basico = db.query(Plano).filter(Plano.nome == "Basico").first()
        if not plano_teste or not plano_basico:
            print("Planos Teste/Basico não encontrados. Execute POST /criar-planos primeiro.")
            return

        # 3. Usuário A (teste@teste.com) - Basico
        ua = db.query(User).filter(User.email == "teste@teste.com").first()
        if not ua:
            ua = User(
                email="teste@teste.com",
                hashed_password=hash_senha("senha123"),
                plano_id=plano_basico.id,
            )
            db.add(ua)
            db.flush()
            db.add(Empresa(cnpj="11111111000111", razao_social="Empresa A Teste", user_id=ua.id))
            print("Usuário teste@teste.com criado (Empresa A).")
        else:
            if not db.query(Empresa).filter(Empresa.user_id == ua.id).first():
                db.add(Empresa(cnpj="11111111000111", razao_social="Empresa A Teste", user_id=ua.id))
                print("Empresa A vinculada ao teste@teste.com.")

        # 4. Usuário B (outro@teste.com) - Basico
        ub = db.query(User).filter(User.email == "outro@teste.com").first()
        if not ub:
            ub = User(
                email="outro@teste.com",
                hashed_password=hash_senha("senha123"),
                plano_id=plano_basico.id,
            )
            db.add(ub)
            db.flush()
            db.add(Empresa(cnpj="22222222000122", razao_social="Empresa B Teste", user_id=ub.id))
            print("Usuário outro@teste.com criado (Empresa B).")
        else:
            if not db.query(Empresa).filter(Empresa.user_id == ub.id).first():
                db.add(Empresa(cnpj="22222222000122", razao_social="Empresa B Teste", user_id=ub.id))
                print("Empresa B vinculada ao outro@teste.com.")

        # 5. Usuário com limite (limite@teste.com) - Plano Teste
        ul = db.query(User).filter(User.email == "limite@teste.com").first()
        if not ul:
            ul = User(
                email="limite@teste.com",
                hashed_password=hash_senha("senha123"),
                plano_id=plano_teste.id,
            )
            db.add(ul)
            db.flush()
            db.add(Empresa(cnpj="33333333000133", razao_social="Empresa Limite", user_id=ul.id))
            print("Usuário limite@teste.com criado (plano Teste, limite_analises=2).")
        else:
            ul.plano_id = plano_teste.id
            if not db.query(Empresa).filter(Empresa.user_id == ul.id).first():
                db.add(Empresa(cnpj="33333333000133", razao_social="Empresa Limite", user_id=ul.id))
            print("Usuário limite@teste.com atualizado (plano Teste, limite_analises=2).")

        db.commit()
        print("\nPronto. Use:")
        print("  USER_A_EMAIL=teste@teste.com USER_A_PASS=senha123")
        print("  USER_B_EMAIL=outro@teste.com USER_B_PASS=senha123")
        print("  USER_LIMITE=limite@teste.com USER_LIMITE_PASS=senha123")
        print("  python scripts/testes_operacionais.py")
    finally:
        db.close()


if __name__ == "__main__":
    main()

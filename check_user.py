"""Script temporário para verificar usuário no banco - será removido após uso"""
import sqlite3
import sys

conn = sqlite3.connect("test.db")
cur = conn.cursor()
cur.execute("SELECT id, email, hashed_password FROM usuarios WHERE email = ?", ("teste@teste.com",))
row = cur.fetchone()
conn.close()

if row:
    print("USUARIO_EXISTE: SIM")
    print("ID:", row[0])
    print("EMAIL:", row[1])
    h = str(row[2])
    print("HASH_COMPLETO:", h)
    print("PREFIXO:", h[:50] if len(h) > 50 else h)
else:
    print("USUARIO_EXISTE: NAO")
    # Listar usuários existentes para referência
    conn = sqlite3.connect("test.db")
    cur = conn.cursor()
    cur.execute("SELECT id, email FROM usuarios")
    users = cur.fetchall()
    conn.close()
    print("USUARIOS_EXISTENTES:", [u[1] for u in users] if users else "Nenhum")

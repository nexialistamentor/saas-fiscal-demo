import sqlite3

conn = sqlite3.connect("test.db")
cur = conn.cursor()

try:
    cur.execute(
        "INSERT INTO planos (nome, limite_cnpjs, limite_analises) VALUES (?, ?, ?)",
        ("Basico", 5, 100),
    )
    print("Basico criado")

    cur.execute(
        "INSERT INTO planos (nome, limite_cnpjs, limite_analises) VALUES (?, ?, ?)",
        ("Pro", 20, 1000),
    )
    print("Pro criado")

    cur.execute(
        "INSERT INTO planos (nome, limite_cnpjs, limite_analises) VALUES (?, ?, ?)",
        ("Ilimitado", 999, 999999),
    )
    print("Ilimitado criado")

    conn.commit()
except sqlite3.IntegrityError:
    print("Planos já existentes")

conn.close()
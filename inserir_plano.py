import sqlite3

conn = sqlite3.connect("test.db")
cur = conn.cursor()

cur.execute("INSERT INTO planos (nome, limite_cnpjs) VALUES (?, ?)", ("Basico", 5))
conn.commit()

cur.execute("SELECT * FROM planos;")
print("PLANOS:", cur.fetchall())

conn.close()
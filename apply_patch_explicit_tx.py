path = r"C:\dev\solveris-b02-g5-v5-publicacao\materializar_cadeia_g5r1_389cce04.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = "    with Session(owner_engine) as session, session.begin():\n        conn = session.connection()"
new = "    with Session(owner_engine) as session:\n        session.begin()\n        conn = session.connection()"
if old not in content: raise SystemExit("A_NOT_FOUND")
content = content.replace(old, new)

old2 = '''    with Session(writer_engine) as wsession, wsession.begin():
        wconn = wsession.connection()'''
new2 = '''    with Session(writer_engine) as wsession:
        wsession.begin()
        wconn = wsession.connection()'''
if old2 not in content: raise SystemExit("B_NOT_FOUND")
content = content.replace(old2, new2)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("PATCHED")

path = r"C:\dev\solveris-b02-g5-v5-publicacao\materializar_cadeia_g5r1_389cce04.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = 'sys.path.insert(0, r"C:\\dev\\solveris-b02-g5-v5-publicacao")'
new = ('sys.path.insert(0, r"C:\\dev\\solveris-b02-g5-v5-publicacao")\n'
       'os.environ["DATABASE_URL"] = "postgresql+psycopg2://solveris_test:solveris_test@localhost:55432/solveris_b02_r4g_test"')
if old not in content:
    raise SystemExit("NOT_FOUND")
content = content.replace(old, new, 1)
with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("PATCHED")

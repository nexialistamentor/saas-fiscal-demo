import re

path = r"C:\dev\solveris-b02-g5-v5-publicacao\migrations\candidates\0065_b02_g5_one_shot_real_CANDIDATE.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

m = re.search(r'_SQL\s*=\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
if not m:
    raise SystemExit("SQL_NOT_FOUND")
sql_text = m.group(1).encode().decode("unicode_escape")

with open(r"C:\dev\solveris-b02-g5-v5-publicacao\extracted_0065.sql", "w", encoding="utf-8") as f:
    f.write(sql_text)
print("EXTRACTED, length =", len(sql_text))

path = r"C:\dev\solveris-b02-g5-v5-publicacao\native\g5\historical_20261022\b02_g5_native_signature.c"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '#include <openssl/evp.h>\n'
new = '#include <openssl/evp.h>\n\nPG_MODULE_MAGIC;\n'

if old not in content:
    raise SystemExit("ANCHOR_NOT_FOUND")
content = content.replace(old, new, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("PATCHED")

path = r"C:\dev\solveris-b02-g5-v5-publicacao\native\g5\historical_20261022\b02_g5_approved_roots.h"
with open(path, encoding="utf-8") as f:
    content = f.read()

# The V1 entry got an extra backslash layer by mistake. Fix: \\" -> \"
before = content.count('\\\\"')
content = content.replace('\\\\"', '\\"')
after = content.count('\\\\"')

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print(f"FIXED: {before} occurrences of double-escaped quote reduced to single (remaining: {after})")

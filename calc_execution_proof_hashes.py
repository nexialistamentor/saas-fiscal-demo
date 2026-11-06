import hashlib, json

def canonical_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',',':'), allow_nan=False).encode('utf-8')

documents = [
    {
        "document_id": "101202501245",
        "sha256": "e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832",
        "byte_size": 258302,
        "url": "https://www.sefanet.pr.gov.br/dados/SEFADOCUMENTOS/101202501245.pdf",
    },
    {
        "document_id": "101201900571",
        "sha256": "af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d",
        "byte_size": 1944929,
        "url": "https://www.sefanet.pr.gov.br/dados/SEFADOCUMENTOS/101201900571.pdf",
    },
]

for d in documents:
    proof = {
        "schema": "B02_G5_EXECUTION_PROOF_STATIC_V1",
        "document_id": d["document_id"],
        "mode": "LOCAL_CAS_INCORPORATION",
        "artifact_hash": d["sha256"],
        "byte_size": d["byte_size"],
        "cas_object_uri": f"cas+sha256://{d['sha256']}/{d['byte_size']}",
        "source_id": "SEFA-PR-B02-DOCUMENTAL",
        "url": d["url"],
    }
    proof_hash = hashlib.sha256(canonical_bytes(proof)).hexdigest()
    binding = {
        "id": f"B02-G5-{d['document_id']}-V3-execproof",
        "hash": proof_hash,
    }
    print(f"=== {d['document_id']} ===")
    print("PROOF_JSON =", json.dumps(proof, sort_keys=True))
    print("PROOF_HASH =", proof_hash)
    print("BINDING =", json.dumps(binding))
    print()

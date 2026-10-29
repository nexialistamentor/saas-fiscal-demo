#!/usr/bin/env python3
"""B02 G5 V5 policy-only read-only preflight; protected writer distributed separately."""
import hashlib,json
from pathlib import Path
POLICY_ID="SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE"
POLICY_HASH="007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf"
FILE_HASH="bf7cdb951ac8e4fb8e5b8e2a1aa6fa3095fad194cbd5845a0dc0e20afd7a3ae9"
def preflight(repo):
 p=Path(repo)/"POLICY_G5_CANDIDATO_SUCESSOR_OUTUBRO_V5_VERSION_2_PARA_REVISAO.json"
 raw=p.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=FILE_HASH:raise RuntimeError("STOP_FILE_HASH")
 body=json.loads(raw)["policy_candidate_body"]
 canon=json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
 if hashlib.sha256(canon).hexdigest()!=POLICY_HASH:raise RuntimeError("STOP_BODY_HASH")
 if (body["policy_id"],body["policy_version"])!=(POLICY_ID,2):raise RuntimeError("STOP_IDENTITY")
 return {"status":"DRY_RUN_PASS","policy_hash":POLICY_HASH,"db_writes":0}
if __name__=="__main__":
 import argparse
 p=argparse.ArgumentParser();p.add_argument("--repo",default=".")
 print(json.dumps(preflight(p.parse_args().repo)))

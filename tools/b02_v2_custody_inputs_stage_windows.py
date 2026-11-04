#!/usr/bin/env python3
"""B02 V2: pin canonical documentary inputs for an explicit custody act.

PREPARE writes only a stage outside custody, preserving the signed original.
INSTALL accepts the SHA256 of that exact stage manifest only AFTER separate
competent authorization; it does not issue ROOT, adopt ROOT or provision trust.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import urllib.request

from app.services import enterprise_b02_founder_review_profile as profile
from tools import b02_v2_custody_root_preflight_windows as check

ROOT = Path(__file__).resolve().parents[1]
CUSTODY = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "SOLVERIS/B02Trust/SUCCESSOR_V3"
STAGE = Path.home() / "Downloads/B02_V2_CUSTODY_INPUTS_STAGE_20261104"
BUNDLE = Path.home() / "Downloads/SOLVERIS_B02_ASSINATURA_AUTORIZADA_20261022/BUNDLE_SUCESSOR_V2_24H_20261103_1800UTC"
PLAN = Path.home() / "Downloads/B02_STORE_V2_PLANO_REVALIDADO_20261104.json"
PUBLIC = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "SOLVERIS/CustodiaB02/Chave_ceee5bb6f2a740a58cf4dbaa66565698/miguel-public.der"


def stop(code):
    raise RuntimeError("STOP_B02_CUSTODY_STAGE_" + code)


def api(url):
    request=urllib.request.Request(url,headers={
        "Accept":"application/vnd.github+json","User-Agent":"SOLVERIS-B02-custody-source-stage"})
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status!=200 or response.geturl()!=url:
            stop("GITHUB_SOURCE_REDIRECT")
        return json.load(response)


def sources():
    _,plan=check.read(PLAN,check.PLAN_SHA)
    observed,auth_sha,adopt,review=check.root_inputs(
        ROOT,plan,CUSTODY,BUNDLE,PUBLIC)
    items={}
    for name,digest in check.SIGNED.items():
        items["BUNDLE_ASSINADO/"+name]=check.read(BUNDLE/name,digest,json_file=(name!="signature.bin"))[0]
    items["CONTINUITY_ADOPTION.json"]=check.read(
        ROOT/"evidence/b02/B02_G4_CONTINUIDADE_DOCUMENTAL_V2_ADOCAO_EMITIDA_20261103.json",
        check.ADOPTION_SHA)[0]
    blob=api("https://api.github.com/repos/nexialistamentor/saas-fiscal-demo/git/blobs/"+check.REVIEW_BLOB)
    if blob.get("sha")!=check.REVIEW_BLOB or blob.get("encoding")!="base64":
        stop("SIGNER_REVIEW_REMOTE_SOURCE")
    review_raw=base64.b64decode(blob["content"])
    if check.sha(review_raw)!=check.REVIEW_SHA or check.blob_sha(review_raw)!=check.REVIEW_BLOB:
        stop("SIGNER_REVIEW_PIN")
    items["SIGNER_REVIEW.json"]=review_raw
    comment=api(check.OWNER_URL)
    if (comment.get("id")!=check.OWNER_COMMENT or
        comment.get("user",{}).get("login")!="nexialistamentor" or
        comment.get("user",{}).get("id")!=192223328 or
        comment.get("author_association")!="OWNER" or
        comment.get("created_at")!=comment.get("updated_at") or
        comment.get("issue_url")!="https://api.github.com/repos/nexialistamentor/saas-fiscal-demo/issues/28"):
        stop("SIGNER_AUTHORITY_SOURCE")
    raw=comment["body"].encode("utf-8")
    auth=profile.parse(raw)
    if (check.sha(raw)!=auth_sha or
        auth["review"]["review_sha256"]!=check.REVIEW_SHA or
        auth["signer_source_git_blob"]!="f1e866ba31d02a5e6c7f99c80d1e9833a9a0bbc2" or
        auth["signing_authorized"] is not True or auth["revoked"] is not False):
        stop("SIGNER_AUTHORITY_BYTES")
    items["SIGNER_AUTHORITY.json"]=raw
    assert len(items)==13
    return plan,observed,items


def write_once(path,raw):
    path=check.safe(path)
    if path.exists():
        if not path.is_file() or path.read_bytes()!=raw:
            stop("EXISTING_BYTES_DIVERGENCE:"+str(path))
        return "PRESENT_MATCH"
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_BINARY",0),0o600)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        raise
    if path.read_bytes()!=raw:
        stop("READBACK_FAILED:"+str(path))
    return "CREATED_READBACK_PASS"


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",choices=("prepare","install"),required=True)
    ap.add_argument("--authorized-stage-sha256")
    a=ap.parse_args()
    plan,observed,items=sources()
    manifest={
        "schema":"SOLVERIS-B02-V2-EXACT-CUSTODY-INPUTS-STAGE-V1",
        "status":"SOURCE_STAGE_NOT_AUTHORITY",
        "source_plan_sha256":check.PLAN_SHA,
        "custody_root":str(check.safe(CUSTODY)),
        "sources":{name:check.sha(raw) for name,raw in sorted(items.items())},
        "root_issued":False,"root_adopted":False,"sql_writes":0}
    can=profile.canonical(manifest)
    stage_sha=check.sha(can)
    if a.mode=="prepare":
        for name,raw in items.items():
            write_once(STAGE/name,raw)
        write_once(STAGE/"manifest.json",can)
        print(json.dumps({
            "status":"THIRTEEN_SOURCES_STAGED_OUTSIDE_CUSTODY",
            "stage_manifest_sha256":stage_sha,
            "stage_path":str(STAGE),
            "source_count":len(items),"custody_writes":0,
            "root_issued":False,"sql_writes":0},sort_keys=True))
        return
    if a.authorized_stage_sha256!=stage_sha:
        stop("SEPARATE_EXACT_STAGE_APPROVAL_REQUIRED")
    if check.read(STAGE/"manifest.json",stage_sha)[0]!=can:
        stop("STAGE_CHANGED")
    for name,raw in items.items():
        if check.read(STAGE/name,check.sha(raw),json_file=(name!="BUNDLE_ASSINADO/signature.bin"))[0]!=raw:
            stop("STAGE_BYTES_CHANGED")
    receipt={name:write_once(CUSTODY/name,raw) for name,raw in items.items()}
    print(json.dumps({
        "status":"DOCUMENTARY_INPUTS_CUSTODY_READBACK_PASS_NO_ROOT",
        "stage_manifest_sha256":stage_sha,"readback":receipt,
        "root_issued":False,"root_adopted":False,"sql_writes":0},sort_keys=True))


if __name__=="__main__":
    try: main()
    except Exception as e:
        print(str(e)[:450],file=__import__("sys").stderr)
        raise SystemExit(2) from None

#!/usr/bin/env python3
"""B02: precise read-only check of six emitted CAS and ROOT input sources.

No ROOT, no ROOT_ADOPTION, no CAS writes, no authority creation, no SQL and
no signing. A candidate for ROOT cannot be passed off as an issued ROOT.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

from app.services import enterprise_b02_founder_review_profile as profile

PLAN_SHA = "e0f9a105b604266e9e0e6a1366f2df499917eb65015dcf22f5db289f43c9f340"
SIGNED = {
    "decision.json": "d3602168c53debd10421aa83d1e980c632870b660be18a451d5b5a3d998c6520",
    "manifest.json": "99d1a424015fc03a5ece71e84341eee748fd0b2fc1bebd238f9df2ede253a6c1",
    "signature.bin": "479c9304724e0a92a5d02145e74d99485792b6e8e54b6c098590d3e0c3ca2c8c",
    "execution.json": "5cdc4e6fca726edbc14aeb7cf253739cca9dc6067d7895096211ee89c0b6e903",
    "history.json": "8c585bdb3ec42d2ebc100f96013ff7be5144d78a1b29435f4025670c6bcd36c1",
    "institutional.json": "c3c894710010c9ffa508e8c7d73ecafefcf02962c38a65f06e50ae4164fcd505",
    "mandates.json": "89630a184206bbb606544151e0925efed29f618125cd3c0099dc9f72854504d6",
    "object.json": "615c8d6466871a94981358e9cab6f4f5d797f317b9026c77e304b7af6ac50906",
    "proofs.json": "9bc79ef8f1cc39d857a41fbfb0e74f0cf4deda274998db23c524c448c88ca004",
    "review.json": "9949a7cca164f9ed50f2b92aa2a1f348fdddfc1c4c3a5cced56b292112a86d21",
}
ADOPTION_SHA = "d0cd1765ea2ef4870a530f8e5367cdde8550b5a60a3a70cb294f9d80678f7fa8"
REVIEW_SHA = "34353ce4dad00bbd3e8a9fc04ed66929d5f952054138d9c127cd7664d0f9b3fe"
REVIEW_BLOB = "4f4fec7dba218991983f1edf07edbdcec828862a"
REVIEW_COMMIT = "bc40bd71316e430f3e42d7fa1ee4a6cc912dfd00"
REVIEW_PATH = "evidence/b02/pareceres_publicados_20261104/B02_SIGNER_V2_PARECER_PROPRIO_FINAL_DELTA_SELETOR_20261104.json"
OWNER_COMMENT = 6629393455
OWNER_URL = ("https://api.github.com/repos/nexialistamentor/"
             "saas-fiscal-demo/issues/comments/6629393455")
PUBLIC_SHA = "6f0ede1267a208505b2443d765cf97f2206759049f938a1d95d92a86c4c5d63c"


def stop(code):
    raise RuntimeError("STOP_B02_ROOT_PREFLIGHT_" + code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def safe(path):
    p = Path(path).absolute()
    if any(x.is_symlink() or (hasattr(x, "is_junction") and x.is_junction())
           for x in (p, *p.parents)):
        stop("SYMLINK_OR_JUNCTION:" + str(path))
    return p


def read(path, expected=None, *, json_file=True):
    path = safe(path)
    if not path.is_file():
        stop("SOURCE_UNAVAILABLE:" + str(path))
    raw = path.read_bytes()
    if expected and sha(raw) != expected:
        stop("SOURCE_SHA256_DIVERGENCE:" + str(path))
    if json_file:
        return raw, profile.parse(raw)
    return raw, None


def git(repo, *args):
    proc = subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, timeout=25)
    if proc.returncode:
        stop("GIT_QUERY_FAILED:" + repr(args))
    return proc.stdout.strip()


def blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def root_inputs(repo, plan, custody, source_bundle, public):
    if git(repo, "branch", "--show-current") != b"candidate/g5-v5-publicacao-local":
        stop("WRONG_CHECKOUT")
    head = git(repo, "rev-parse", "HEAD").decode()
    approved_head = plan["source_git_head"]
    if git(repo, "merge-base", "--is-ancestor", approved_head, head) not in (b"",):
        stop("PLAN_SOURCE_NOT_ANCESTOR")
    path = "tools/b02_store_emission_v2_windows.py"
    current_blob = git(repo, "rev-parse", "HEAD:" + path)
    approved_blob = git(repo, "rev-parse", approved_head + ":" + path)
    if current_blob != approved_blob:
        stop("STORE_EMITTER_SOURCE_CHANGED")
    if str(safe(custody)) != plan["custody_root"]:
        stop("CUSTODY_ROOT_VS_PLAN")
    if plan["status"] != "PLAN_NOT_AUTHORITY" or plan["postgresql_writes"] != 0:
        stop("PLAN_IS_NOT_PREVIEW")
    for name, pin in plan["pins"].items():
        expected = plan["objects"][name]
        raw, actual = read(custody / "STORE" / "sha256" /
                           pin["sha256"][:2] / (pin["sha256"] + ".json"),
                           pin["sha256"])
        if actual != expected or actual.get("id") != pin["id"]:
            stop("CAS_READBACK_DIVERGENCE:" + name)
    for name, digest in SIGNED.items():
        read(source_bundle / name, digest, json_file=(name != "signature.bin"))
    if plan["signed_bundle_hashes"] != SIGNED:
        stop("PLAN_SIGNED_SOURCE_DIVERGENCE")
    public_raw, _ = read(public, PUBLIC_SHA, json_file=False)
    from cryptography.hazmat.primitives.serialization import load_der_public_key
    try:
        key = load_der_public_key(public_raw)
        key.verify((source_bundle / "signature.bin").read_bytes(),
                   (source_bundle / "decision.json").read_bytes())
    except Exception:
        stop("SIGNED_DECISION_ED25519_INVALID")
    observed = {}
    bundle_target = custody / "BUNDLE_ASSINADO"
    observed["BUNDLE_ASSINADO"] = {
        "status": "PRESENT_MATCH" if bundle_target.is_dir() else "MISSING",
        "files": 10 if bundle_target.is_dir() else 0,
    }
    if bundle_target.is_dir():
        if {p.name for p in bundle_target.iterdir()} != set(SIGNED):
            stop("CUSTODY_SIGNED_BUNDLE_FILE_SET")
        for name,digest in SIGNED.items():
            read(bundle_target / name,digest,json_file=(name != "signature.bin"))
    adoption_path = repo / "evidence" / "b02" / "B02_G4_CONTINUIDADE_DOCUMENTAL_V2_ADOCAO_EMITIDA_20261103.json"
    adoption_raw, adoption = read(adoption_path, ADOPTION_SHA)
    dest = custody / "CONTINUITY_ADOPTION.json"
    observed["CONTINUITY_ADOPTION.json"] = "PRESENT_MATCH" if dest.is_file() else "MISSING"
    if dest.is_file():
        raw,_ = read(dest,ADOPTION_SHA)
        if raw != adoption_raw:
            stop("CONTINUITY_ADOPTION_DIVERGENCE")
    review_url=("https://api.github.com/repos/nexialistamentor/"
                "saas-fiscal-demo/git/blobs/"+REVIEW_BLOB)
    request=urllib.request.Request(review_url,headers={
        "Accept":"application/vnd.github+json", "User-Agent":"SOLVERIS-B02-root-readonly"})
    with urllib.request.urlopen(request,timeout=15) as response:
        if response.status!=200 or response.geturl()!=review_url:
            stop("REVIEW_GITHUB_SOURCE_INVALID")
        gitblob=json.load(response)
    if gitblob.get("sha")!=REVIEW_BLOB or gitblob.get("encoding")!="base64":
        stop("REVIEW_GITHUB_BLOB_UNPINNED")
    review_raw=base64.b64decode(gitblob["content"],validate=False)
    if (len(review_raw)!=gitblob.get("size") or
        blob_sha(review_raw) != REVIEW_BLOB or sha(review_raw) != REVIEW_SHA):
        stop("REVIEW_SOURCE_UNPINNED")
    review = profile.parse(review_raw)
    if review.get("outcome") != "favoravel" or review.get("conflicts") != []:
        stop("REVIEW_NOT_FAVORABLE")
    dest = custody / "SIGNER_REVIEW.json"
    observed["SIGNER_REVIEW.json"] = "PRESENT_MATCH" if dest.is_file() else "MISSING"
    if dest.is_file() and read(dest, REVIEW_SHA)[0] != review_raw:
        stop("SIGNER_REVIEW_DIVERGENCE")
    req = urllib.request.Request(OWNER_URL, headers={
        "Accept":"application/vnd.github+json", "User-Agent":"SOLVERIS-B02-root-readonly"})
    with urllib.request.urlopen(req, timeout=15) as response:
        if response.status != 200 or response.geturl() != OWNER_URL:
            stop("OWNER_ADOPTION_URL")
        comment=json.load(response)
    if (comment.get("id") != OWNER_COMMENT or
        comment.get("user",{}).get("login") != "nexialistamentor" or
        comment.get("user",{}).get("id") != 192223328 or
        comment.get("author_association") != "OWNER" or
        comment.get("created_at") != comment.get("updated_at") or
        comment.get("issue_url") !=
         "https://api.github.com/repos/nexialistamentor/saas-fiscal-demo/issues/28"):
        stop("OWNER_ADOPTION_SOURCE_INVALID")
    authority_raw = comment["body"].encode("utf-8")
    authority = profile.parse(authority_raw)
    if (authority.get("issuer") != "Miguel" or
        authority.get("signer_source_git_blob") !=
          "f1e866ba31d02a5e6c7f99c80d1e9833a9a0bbc2" or
        authority.get("review",{}).get("review_sha256") != REVIEW_SHA or
        authority.get("signing_authorized") is not True or
        authority.get("approved") is not True or authority.get("revoked") is not False):
        stop("OWNER_ADOPTION_VS_FINAL_SIGNER")
    dest = custody / "SIGNER_AUTHORITY.json"
    observed["SIGNER_AUTHORITY.json"] = "PRESENT_MATCH" if dest.is_file() else "MISSING"
    if dest.is_file() and read(dest,sha(authority_raw))[0] != authority_raw:
        stop("SIGNER_AUTHORITY_DIVERGENCE")
    for item in ("ROOT.json","ROOT_ADOPTION.json"):
        observed[item] = "ALREADY_EXISTS_REQUIRES_SEPARATE_VALIDATION" if (
            custody/item).exists() else "NOT_ISSUED"
    return observed,sha(authority_raw),adoption,review


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument("--plan",type=Path,default=Path.home()/"Downloads/B02_STORE_V2_PLANO_REVALIDADO_20261104.json")
    ap.add_argument("--custody",type=Path,default=Path(os.environ.get("LOCALAPPDATA",Path.home()/"AppData/Local"))/"SOLVERIS/B02Trust/SUCCESSOR_V3")
    ap.add_argument("--signed-bundle",type=Path,default=Path.home()/"Downloads/SOLVERIS_B02_ASSINATURA_AUTORIZADA_20261022/BUNDLE_SUCESSOR_V2_24H_20261103_1800UTC")
    ap.add_argument("--public-der",type=Path,default=Path(os.environ.get("LOCALAPPDATA",Path.home()/"AppData/Local"))/"SOLVERIS/CustodiaB02/Chave_ceee5bb6f2a740a58cf4dbaa66565698/miguel-public.der")
    a=ap.parse_args()
    _,plan=read(a.plan,PLAN_SHA)
    now=datetime.now(timezone.utc)
    observed,signer_sha,adoption,review=root_inputs(
        a.repo.resolve(),plan,a.custody,a.signed_bundle,a.public_der)
    snap=plan["objects"]["snapshot"]
    start=datetime.fromisoformat(snap["valid_from"])
    end=datetime.fromisoformat(snap["valid_until"])
    print(json.dumps({
        "status":"ROOT_INPUTS_PHYSICAL_READ_ONLY_INSPECTED_NO_ROOT",
        "plan_sha256":PLAN_SHA,
        "six_cas_readback":"PASS",
        "signed_bundle_ed25519":"MATHEMATICAL_PASS_NO_AUTHORITY",
        "signer_authority_sha256":signer_sha,
        "signer_review_sha256":REVIEW_SHA,
        "continuity_adoption_sha256":ADOPTION_SHA,
        "snapshot_sha256":plan["pins"]["snapshot"]["sha256"],
        "root_issuance_deadline_utc":start.isoformat(),
        "signed_decision_until_utc":end.isoformat(),
        "root_issuance_still_prospective":now<=start,
        "custody_inputs":observed,
        "custody_writes":0,"sql_writes":0,"root_issued":False,
        "root_adopted":False,"runtime_provisioned":False,"r7_closed":False
    },sort_keys=True))


if __name__ == "__main__":
    try: main()
    except Exception as e:
        print(str(e)[:400],file=sys.stderr)
        raise SystemExit(2) from None

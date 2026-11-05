"""Parse an expressly synthetic nfeProc for B02 pipeline evidence only.

This does not validate XML schema, signature, real SEFAZ authorization or tax.
The public R7 real-fiscal consumer must not accept this receipt.
"""
from __future__ import annotations
import hashlib
import re
from xml.etree import ElementTree as ET

NS = "{http://www.portalfiscal.inf.br/nfe}"
NCMS = {"12119090", "27121000", "28142000"}

def inspect_synthetic_nfeproc(xml_bytes: bytes):
    if not isinstance(xml_bytes, bytes) or len(xml_bytes) > 100000 or b"<!DOCTYPE" in xml_bytes.upper():
        raise ValueError("STOP_R6_SYNTHETIC_INPUT")
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError("STOP_R6_SYNTHETIC_PARSE") from exc
    if root.tag != NS + "nfeProc" or root.attrib.get("synthetic_only") != "true":
        raise ValueError("STOP_R6_SYNTHETIC_MARKER_REQUIRED")
    inf = root.find("./" + NS + "NFe/" + NS + "infNFe")
    if inf is None or inf.attrib.get("Id") != "NFeSYNTHETIC_NOT_A_REAL_ACCESS_KEY":
        raise ValueError("STOP_R6_SYNTHETIC_FIXED_NONFISCAL_ID_REQUIRED")
    items=[]
    for det in inf.findall("./" + NS + "det"):
        prod = det.find("./" + NS + "prod")
        if prod is None:
            raise ValueError("STOP_R6_SYNTHETIC_ITEM_MISSING")
        ncm=prod.findtext(NS + "NCM", default="")
        if ncm not in NCMS:
            raise ValueError("STOP_R6_SYNTHETIC_C3_NCM_REQUIRED")
        if not re.fullmatch(r"[1-9][0-9]*", det.attrib.get("nItem", "")):
            raise ValueError("STOP_R6_SYNTHETIC_ITEM_NUMBER")
        items.append({"nItem": int(det.attrib["nItem"]), "ncm":ncm,
             "cest":prod.findtext(NS + "CEST",default=""),
             "cfop":prod.findtext(NS + "CFOP",default=""),
             "description":prod.findtext(NS + "xProd",default="")})
    if not items:
        raise ValueError("STOP_R6_SYNTHETIC_NO_ITEMS")
    return {"status":"R6_SYNTHETIC_PIPELINE_ONLY_NOT_FISCAL",
       "synthetic_only":True,"xml_sha256":hashlib.sha256(xml_bytes).hexdigest(),
       "items":items,"fiscal_authority_verified":False,
       "real_fiscal_link_completed":False,"r7_real_consumer_eligible":False}

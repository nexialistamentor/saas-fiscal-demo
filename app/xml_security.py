"""
Proteções operacionais para upload de XML fiscais.
Evita XML muito grande, tipo incorreto e ataques XXE (DOCTYPE/ENTITY).
"""
import unicodedata

import defusedxml.ElementTree as ET
from fastapi import HTTPException, UploadFile

MAX_XML_SIZE_BYTES = 2 * 1024 * 1024  # 2MB limite real seguro
ALLOWED_CONTENT_TYPES = ("application/xml", "text/xml")
ALLOWED_EXTENSIONS = (".xml",)
# Extensões executáveis bloqueadas (upload malicioso)
BLOCKED_EXTENSIONS = (".exe", ".py", ".pyc", ".sh", ".bat", ".cmd", ".ps1", ".dll", ".so", ".bin")
# Padrões maliciosos que indicam tentativa de XXE
XXE_BLOCKED_PATTERNS = (
    "<!DOCTYPE",
    "<!ENTITY",
    "SYSTEM",
    "PUBLIC",
    "ENTITY",
)


async def validar_upload_xml(file: UploadFile) -> bytes:
    """
    Valida arquivo XML de upload e retorna o conteúdo em bytes.
    Levanta HTTPException(400) se:
    - Tamanho > 2MB
    - Tipo/extensão não é XML
    - Conteúdo contém DOCTYPE ou ENTITY (proteção XXE)
    """
    conteudo = b""
    while chunk := await file.read(1024 * 64):  # lê em blocos de 64KB
        conteudo += chunk
        if len(conteudo) > MAX_XML_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"XML muito grande. Limite: {MAX_XML_SIZE_BYTES // (1024*1024)} MB",
            )

    # Proteção adicional: limite de caracteres após decode
    if len(conteudo) > MAX_XML_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="XML excede limite seguro de processamento",
        )

    if len(conteudo) == 0:
        raise HTTPException(status_code=400, detail="Arquivo vazio")

    # Bloquear extensões executáveis
    filename = (file.filename or "").lower()
    if any(filename.endswith(ext) for ext in BLOCKED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail="Tipo de arquivo não permitido para upload",
        )

    # Validação de tipo
    content_type = (file.content_type or "").lower().split(";")[0].strip()

    # Regra rígida: precisa ser XML válido E extensão .xml
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Content-Type inválido para XML",
        )

    if not any(filename.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail="Extensão inválida. Apenas .xml permitido",
        )

    # Proteção XXE: bloquear DOCTYPE e ENTITY
    try:
        texto = unicodedata.normalize("NFKC", conteudo.decode("utf-8", errors="strict")).upper()
    except Exception:
        raise HTTPException(status_code=400, detail="Conteúdo inválido ou encoding suspeito")

    for padrao in XXE_BLOCKED_PATTERNS:
        if padrao.upper() in texto:
            raise HTTPException(
                status_code=400,
                detail="XML contém conteúdo potencialmente malicioso (XXE bloqueado)",
            )

    # Remover BOM se existir
    conteudo_limpo = conteudo.lstrip(b"\xef\xbb\xbf").lstrip()

    # Validação estrutural mínima
    inicio = conteudo_limpo[:20].upper()

    if not (inicio.startswith(b"<?XML") or inicio.startswith(b"<NFE") or inicio.startswith(b"<")):
        raise HTTPException(
            status_code=400,
            detail="Arquivo não parece ser um XML válido",
        )

    try:
        ET.fromstring(conteudo_limpo)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="XML malformado ou inválido",
        )

    return conteudo

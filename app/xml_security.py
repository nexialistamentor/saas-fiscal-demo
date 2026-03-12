"""
Proteções operacionais para upload de XML fiscais.
Evita XML muito grande, tipo incorreto e ataques XXE (DOCTYPE/ENTITY).
"""
from fastapi import HTTPException, UploadFile

MAX_XML_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_CONTENT_TYPES = ("application/xml", "text/xml")
ALLOWED_EXTENSIONS = (".xml",)
# Extensões executáveis bloqueadas (upload malicioso)
BLOCKED_EXTENSIONS = (".exe", ".py", ".pyc", ".sh", ".bat", ".cmd", ".ps1", ".dll", ".so", ".bin")
# Padrões maliciosos que indicam tentativa de XXE
XXE_BLOCKED_PATTERNS = ("<!DOCTYPE", "<!ENTITY")


async def validar_upload_xml(file: UploadFile) -> bytes:
    """
    Valida arquivo XML de upload e retorna o conteúdo em bytes.
    Levanta HTTPException(400) se:
    - Tamanho > 5MB
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
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        if not any(filename.endswith(ext) for ext in ALLOWED_EXTENSIONS):
            raise HTTPException(
                status_code=400,
                detail="Tipo de documento inválido. Envie um arquivo XML.",
            )

    # Proteção XXE: bloquear DOCTYPE e ENTITY
    try:
        texto = conteudo.decode("utf-8", errors="ignore").upper()
    except Exception:
        raise HTTPException(status_code=400, detail="Conteúdo não é texto válido")

    for padrao in XXE_BLOCKED_PATTERNS:
        if padrao.upper() in texto:
            raise HTTPException(
                status_code=400,
                detail="XML contém conteúdo potencialmente malicioso (XXE bloqueado)",
            )

    return conteudo

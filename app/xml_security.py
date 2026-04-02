"""
Proteções operacionais para upload de XML fiscais.

Camadas de defesa (ordem de prioridade):
1. Parser seguro (defusedxml) — proteção primária contra XXE/bombs
2. Nome de ficheiro seguro (UUID) — elimina path traversal
3. Content-Type obrigatório — rejeita uploads ambíguos
4. Heurística XXE (DOCTYPE/ENTITY) — camada complementar
"""
import unicodedata
import uuid

import defusedxml.ElementTree as ET
from fastapi import HTTPException, UploadFile

MAX_XML_SIZE_BYTES = 2 * 1024 * 1024  # 2MB limite real seguro
ALLOWED_CONTENT_TYPES = ("application/xml", "text/xml")
ALLOWED_EXTENSIONS = (".xml",)
BLOCKED_EXTENSIONS = (".exe", ".py", ".pyc", ".sh", ".bat", ".cmd", ".ps1", ".dll", ".so", ".bin")
XXE_BLOCKED_PATTERNS = (
    "<!DOCTYPE",
    "<!ENTITY",
    "SYSTEM",
    "PUBLIC",
    "ENTITY",
)


def gerar_nome_seguro(extensao: str = ".xml") -> str:
    """Gera nome de ficheiro baseado em UUID4. Nunca usa input do utilizador."""
    return f"{uuid.uuid4().hex}{extensao}"


async def validar_upload_xml(file: UploadFile) -> bytes:
    """
    Valida arquivo XML de upload e retorna o conteúdo em bytes.
    Levanta HTTPException(400) se:
    - Tamanho > 2MB
    - Extensão executável ou não-.xml
    - Content-Type ausente ou não-XML
    - Conteúdo contém DOCTYPE ou ENTITY (proteção XXE)
    """
    conteudo = b""
    while chunk := await file.read(1024 * 64):
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

    # --- Extensão ---
    filename = (file.filename or "").lower()
    if any(filename.endswith(ext) for ext in BLOCKED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail="Tipo de arquivo não permitido para upload",
        )
    if not any(filename.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail="Extensão inválida. Apenas .xml é aceito.",
        )

    # --- Content-Type obrigatório ---
    content_type = (file.content_type or "").lower().split(";")[0].strip()
    if not content_type or content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Content-Type inválido. Envie application/xml ou text/xml.",
        )

    # --- Heurística XXE (camada complementar — defesa em profundidade) ---
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

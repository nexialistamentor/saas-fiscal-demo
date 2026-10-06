"""Compare observed identifiers; never certify identity or fiscal validity.

Comparable means exactly fourteen ASCII digits. This is a format comparison,
not validation of check digits, registry status, signature or XML authenticity.
"""
import re


_CNPJ_COMPARAVEL = re.compile(r"[0-9]{14}", re.ASCII)


def comparar_emitente_observado(*, documento_id, cnpj_empresa, cnpj_emitente):
    if cnpj_emitente is None or cnpj_emitente == "":
        estado = "ausente"
    elif type(cnpj_emitente) is not str or not _CNPJ_COMPARAVEL.fullmatch(cnpj_emitente):
        estado = "invalido"
    elif type(cnpj_empresa) is not str or not _CNPJ_COMPARAVEL.fullmatch(cnpj_empresa):
        estado = "empresa_sem_cnpj_comparavel"
    elif cnpj_emitente == cnpj_empresa:
        estado = "coincidente"
    else:
        estado = "divergente"
    return {
        "documento_id": documento_id,
        "estado": estado,
        "cnpj_emitente_observado": cnpj_emitente,
    }

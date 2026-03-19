from app.database import SessionLocal
from app.models import Empresa
from app.services.registro_analise_service import executar_e_registrar_analise_xml


def processar_xml_job(xml_bytes: bytes, empresa_id: int):
    """Job que executa o pipeline completo de análise de XML e registro em relatorios_analise."""
    db = SessionLocal()
    try:
        emp = db.query(Empresa).filter(Empresa.id == empresa_id).first()
        if not emp or not emp.user_id:
            return None
        rel, analise = executar_e_registrar_analise_xml(
            db=db,
            xml_bytes=xml_bytes,
            user_id=emp.user_id,
            empresa_id=empresa_id,
        )
        return {
            "relatorio_id": rel.id,
            "resultado": analise
        }
    finally:
        db.close()

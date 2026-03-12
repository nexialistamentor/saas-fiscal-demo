from app.models import EngineResultado


class EngineResultadoService:

    def __init__(self, db):
        self.db = db

    def listar_por_empresa(self, empresa_id: int):
        return (
            self.db.query(EngineResultado)
            .filter(EngineResultado.empresa_id == empresa_id)
            .order_by(EngineResultado.criado_em.desc())
            .all()
        )

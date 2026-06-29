"""
MockProvider — devolve JSON estruturado compatível com AgentErroOperacional.
Usado em testes e quando DEEPSEEK_DRY_RUN=true.
"""


class MockProvider:
    modelo = "mock-v1"

    def completar(self, tarefa: str, contexto: dict, max_tokens: int = 1024, temperatura: float = 0.2) -> dict:
        return {
            "provider": "mock",
            "modelo": self.modelo,
            "output": {
                "classificacao": "P2",
                "causa_provavel": "mock — sem chamada real",
                "evidencias": [],
                "ficheiros_provaveis": [],
                "teste_recomendado": "mock",
                "patch_sugerido_texto": None,
                "risco_patch": "baixo",
                "informacao_em_falta": [],
            },
            "dry_run": True,
            "tokens_utilizados": None,
            "latencia_ms": 0,
            "erro": None,
        }

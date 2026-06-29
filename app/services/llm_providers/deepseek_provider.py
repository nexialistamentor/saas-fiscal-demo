"""
DeepSeekProvider — barramento soberano para DeepSeek v4.

REGRAS DE SEGURANÇA (nunca violar):
- Nunca logar DEEPSEEK_API_KEY.
- Nunca enviar ao LLM: CPF, CNPJ, email completo, token, XML fiscal bruto.
- DEEPSEEK_DRY_RUN=true por defeito — chamada real exige flag explícita.
- Output deve ser sempre JSON estruturado; texto livre é erro de contrato.
"""
import os
import re
import time
import json
import httpx


CAMPOS_PROIBIDOS = {
    "cpf", "cnpj", "email", "token", "xml",
    "senha", "password", "authorization", "api_key"
}

# Padrões sensíveis em valores — nunca devem chegar ao LLM
_PADROES_VALOR = [
    (re.compile(r'\b\d{3}[\.\-]?\d{3}[\.\-]?\d{3}[\.\-]?\d{2}\b'), "CPF"),
    (re.compile(r'\b\d{2}[\.\-]?\d{3}[\.\-]?\d{3}[\/\.\-]?\d{4}[\.\-]?\d{2}\b'), "CNPJ"),
    (re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'), "email"),
    (re.compile(r'Bearer\s+[A-Za-z0-9\-_\.]+'), "Bearer token"),
    (re.compile(r'eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]*'), "JWT"),
    (re.compile(r'<NFe|<nfeProc|<enviNFe', re.IGNORECASE), "XML NFe"),
]


def _validar_valores(contexto, caminho: str = "contexto") -> None:
    """Detecta valores sensíveis em strings — CPF, CNPJ, email, token, JWT, XML."""
    if isinstance(contexto, dict):
        for chave, valor in contexto.items():
            _validar_valores(valor, f"{caminho}.{chave}")
    elif isinstance(contexto, list):
        for i, item in enumerate(contexto):
            _validar_valores(item, f"{caminho}[{i}]")
    elif isinstance(contexto, str):
        for padrao, nome in _PADROES_VALOR:
            if padrao.search(contexto):
                raise ValueError(
                    f"Valor em '{caminho}' contém dado sensível ({nome}). "
                    "Sanitize antes de chamar o LLM."
                )


def _validar_contexto(contexto, caminho: str = "contexto") -> None:
    """Sanitização recursiva — bloqueia chave por inclusão em qualquer nível."""
    if isinstance(contexto, dict):
        for chave, valor in contexto.items():
            chave_lower = str(chave).lower()
            if any(campo in chave_lower for campo in CAMPOS_PROIBIDOS):
                raise ValueError(
                    f"Contexto contém campo proibido em {caminho}.{chave}. "
                    "Sanitize antes de chamar o LLM."
                )
            _validar_contexto(valor, f"{caminho}.{chave}")
    elif isinstance(contexto, list):
        for i, item in enumerate(contexto):
            _validar_contexto(item, f"{caminho}[{i}]")


class DeepSeekProvider:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.modelo = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.timeout = int(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "30"))
        self.dry_run = os.getenv("DEEPSEEK_DRY_RUN", "true").lower() == "true"

    def completar(self, tarefa: str, contexto: dict, max_tokens: int = 1024, temperatura: float = 0.2) -> dict:
        _validar_contexto(contexto)
        _validar_valores(contexto)

        if self.dry_run or not self.api_key:
            return {
                "provider": "deepseek",
                "modelo": self.modelo,
                "output": {
                    "classificacao": "dry_run",
                    "causa_provavel": "DEEPSEEK_DRY_RUN=true ou API key ausente",
                    "evidencias": [],
                    "ficheiros_provaveis": [],
                    "teste_recomendado": None,
                    "patch_sugerido_texto": None,
                    "risco_patch": None,
                    "informacao_em_falta": [],
                },
                "dry_run": True,
                "tokens_utilizados": None,
                "latencia_ms": 0,
                "erro": None,
            }

        prompt = (
            f"Tarefa: {tarefa}\n"
            f"Contexto: {json.dumps(contexto, ensure_ascii=False)}\n\n"
            "Responde APENAS com JSON válido, sem texto adicional, "
            "com os campos: classificacao, causa_provavel, evidencias, "
            "ficheiros_provaveis, teste_recomendado, patch_sugerido_texto, "
            "risco_patch, informacao_em_falta."
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.modelo,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperatura,
        }

        inicio = time.time()
        try:
            response = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            latencia_ms = int((time.time() - inicio) * 1000)
            conteudo = data["choices"][0]["message"]["content"]
            output = json.loads(conteudo)
            return {
                "provider": "deepseek",
                "modelo": self.modelo,
                "output": output,
                "dry_run": False,
                "tokens_utilizados": data.get("usage", {}).get("total_tokens"),
                "latencia_ms": latencia_ms,
                "erro": None,
            }
        except json.JSONDecodeError as e:
            return {
                "provider": "deepseek", "modelo": self.modelo,
                "output": {}, "dry_run": False,
                "tokens_utilizados": None, "latencia_ms": int((time.time() - inicio) * 1000),
                "erro": f"Output não é JSON válido: {e}",
            }
        except httpx.HTTPStatusError as e:
            return {
                "provider": "deepseek", "modelo": self.modelo,
                "output": {}, "dry_run": False,
                "tokens_utilizados": None, "latencia_ms": int((time.time() - inicio) * 1000),
                "erro": f"HTTP {e.response.status_code}",
            }
        except Exception as e:
            return {
                "provider": "deepseek", "modelo": self.modelo,
                "output": {}, "dry_run": False,
                "tokens_utilizados": None, "latencia_ms": int((time.time() - inicio) * 1000),
                "erro": str(e),
            }

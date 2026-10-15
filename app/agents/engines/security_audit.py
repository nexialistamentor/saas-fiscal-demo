"""M006-C2: motor de seguranca deterministico sem acessos a dados brutos.

Limiares espelhados do AG4 legado. O contrato de teste detecta divergencia.
Nenhuma decisao de bloqueio ou de suspensao de utilizadores e tomada aqui.
"""
from app.agents.contracts.security_audit import SecurityAuditContext

MAX_CONTAS_POR_IP = 3
MAX_REQUESTS_POR_USER = 100
MAX_REQUESTS_SEM_UA = 20


def avaliar_indicadores(context: SecurityAuditContext) -> list[str]:
    codes: list[str] = []
    if context.max_distinct_accounts_per_ip > MAX_CONTAS_POR_IP:
        codes.append("MULTI_ACCOUNT_PATTERN")
    if context.max_requests_per_user > MAX_REQUESTS_POR_USER:
        codes.append("USER_REQUEST_VOLUME")
    if context.requests_without_user_agent > MAX_REQUESTS_SEM_UA:
        codes.append("MISSING_USER_AGENT_VOLUME")
    return codes

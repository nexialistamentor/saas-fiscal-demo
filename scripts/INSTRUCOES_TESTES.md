# Instruções para Testes Operacionais

## Pré-requisitos

1. **Redis** — precisa estar rodando em `localhost:6379`

   Execute o script auxiliar para instalar/verificar Redis:
   ```powershell
   .\scripts\setup-redis.ps1
   ```

   **Opções manuais no Windows:**
   - **Winget** (mais simples): `winget install Redis.Redis --accept-package-agreements --accept-source-agreements -h`
   - **Chocolatey**: `choco install redis-64 -y` (PowerShell como Administrador)
   - **Docker**: `docker run -d -p 6379:6379 redis`
   - **WSL**: `sudo apt install redis-server` e `sudo service redis-server start`
   - **Memurai**: [memurai.com](https://www.memurai.com/) (compatível com Redis)

2. **Python** — com venv ativado ou pacotes instalados (`requests`, `rq`, `redis`, `uvicorn`)
   ```powershell
   pip install redis rq
   ```

## Comandos exatos (4 terminais)

### Terminal 1 — Redis
```powershell
redis-server
```

### Terminal 2 — Worker
```powershell
cd c:\Users\Oem\OneDrive\Desktop\saas-fiscal-demo
.\venv\Scripts\Activate.ps1
python -m app.workers.analysis_worker
```

### Terminal 3 — API
```powershell
cd c:\Users\Oem\OneDrive\Desktop\saas-fiscal-demo
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

### Terminal 4 — Testes
```powershell
cd c:\Users\Oem\OneDrive\Desktop\saas-fiscal-demo
.\scripts\executar_testes.ps1
```

## O que o script valida

| Teste | Validação | Resultado esperado |
|-------|-----------|-------------------|
| **1 — Carga** | API → Redis → Worker → Motor Fiscal → Banco | ≥45 jobs enfileirados |
| **2 — Isolamento** | Empresa A não acessa dados da Empresa B | HTTP 403 |
| **3 — Limite** | limite_analises do plano funcionando | HTTP 429 na 3ª análise |

## Após os testes

Abrir no navegador: http://localhost:8000/dashboard/analises/1

Resposta esperada:
```json
[{
  "id": 1823,
  "xml_chave": "35240500000000000000",
  "status": "ok",
  "tempo_execucao": 2.8,
  "total_alertas": 3,
  "score": 78
}]
```

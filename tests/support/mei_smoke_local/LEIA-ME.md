# SOLVERIS MEI — smoke local reutilizavel

Este pacote ainda precisa de execucao no Windows do projeto. Foi revisto contra
o commit 4ab12627817fab5f3b9b8f435bbda4c27e4e130e e passa validacao sintatica.
Nao declarar GREEN antes da execucao.

## Objetivo

Cadastro por HTTP, login pelo navegador, recuperacao sem compra, intencao duravel,
checkout canonico, retomada sem nova ordem/cobranca, confirmacao canonica simulada,
autorizacao da competencia paga, PDF de fixture baixado e codigo de barras de
fixture exibido. Repete em 1280px e 390px; outra competencia permanece bloqueada.
Termos e consentimento sao aceites por HTTP nesta conta sintetica.

## Limites

- Banco PostgreSQL 17.10 novo e descartavel, criado com Docker; schema dos modelos
  via create_all, sem provar migrations Alembic.
- Servidores novos em 8766 e 5175; os atuais 8765/5173 ficam abertos.
- Identidade fiscal sintetica. Nenhum contribuinte real ou credencial real.
- Gateway e SERPRO simulados somente no processo test-only.
- A confirmacao chama o escritor canonico, sem fabricar grant ou ignorar
  autenticacao, ownership, intencao ou autoridade por competencia.
- Nao testa assinatura/rececao/reconciliacao de webhook, nem gateway/SERPRO reais.
- O limiter e reposto entre os dois cenarios independentes; nao prova throttle.
- PDF e codigo de barras sao fixtures sem validade fiscal. Nao pagar esse codigo.
- Nao modifica repositorio, flags, deployments ou dominios.
- Rede do backend bloqueada fora de loopback; browser bloqueia externos, exceto
  pagina virtual interceptada de checkout.example.invalid (sem rede externa).
- Fail-closed: HEAD diferente dos dois SHAs revistos ou portas ocupadas abortam.

## Executar

No PowerShell com o venv ativo, depois de extrair este ZIP:

```powershell
python "$env:USERPROFILE\Downloads\SOLVERIS_MEI_smoke_local\run.py" 'C:\dev\saas-fiscal-demo-mei'
```

Requer Docker, psycopg2 no venv, frontend-dashboard/node_modules, Playwright
instalado em _pw_tmp/node_modules e Chromium ja instalado. Nao instala nem
atualiza dependencias. Nao pede login externo.

## Resultado

PASS imprime dois cenarios e SMOKE_SIMULADO=PASS. A pasta de resultados em TEMP
contem metadata, logs, screenshots, fixtures PDF e resultado.json. Em erro,
parar e enviar a mensagem e backend.log/frontend.log; nao alterar producao.
Container e processos filhos sao encerrados no finally. Se houver encerramento
forcado do Python, pode ser necessario remover o container indicado no output.

## Provas anteriores (recebidas do terminal)

- Browser: desktop/mobile, login/dashboard/limite/estimativa, sem overflow/erro JS.
- Contratos recovery/emissao/tela: 101 passed, 80 warnings.
- Contrato economic authority em PostgreSQL: 1 passed, 41 warnings.
- Novo pacote: runtime pendente; nao substitui as provas reais de pagamento/DAS.

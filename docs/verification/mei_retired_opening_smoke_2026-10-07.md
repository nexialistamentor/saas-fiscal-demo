# Retirada do painel publico de abertura de MEI

Revisao testada: 345c4d968169270e4eb8fc4345e099f86f67b7f5.
Resultado: SMOKE_SIMULADO=PASS.
Evidencias locais: C:\Users\Oem\AppData\Local\Temp\solveris-mei-e2e-51nzddg2.

## Cenario corrigido
- Novo cadastro em abertura bloqueado pelo backend: HTTP 409.
- Cadastro legado representado por fixture sintetica no PostgreSQL descartavel.
- 1280px e 390px: acesso pendente, sem oferta de abertura ou pedidos fiscais.
- Dados preservados, recarregamento e logout aprovados.
- Sem overflow ou erros JavaScript nos controles executados.

## Regressao
- Conferencia documental, natureza, finalidade e CFOPs por item aprovados.
- Ausencias, texto escapado, troca de ano e erro 503 aprovados.
- Checkout, retomada, confirmacao simulada, PDF, codigo de barras e isolamento por competencia aprovados.

## Limites
- Pagamento, webhook e SERPRO reais nao testados neste smoke.
- Producao nao alterada por esta prova.
- Runner fixado na revisao testada; outro HEAD exige revisao explicita.
- Scripts de servidor e fixture sao exclusivos de teste local; nunca publicar.
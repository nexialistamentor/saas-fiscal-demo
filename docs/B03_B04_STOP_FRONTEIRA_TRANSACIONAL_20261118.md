# SOLVERIS B03/B04 — STOP de fronteira transacional para integração opt-in

Data: 18/11/2026. Estado: **investigação causal e preservação; sem código de produto alterado**.

## Autoridade e linhagem

- Miguel ratificou uma intervenção cirúrgica no **escritor XML compartilhado**,
  somente no ambiente de recuperação e mantendo integralmente os consumidores
  legados/MEI. Essa ratificação não especificou modificações transacionais nos
  outros serviços compartilhados.
- Branch remoto documental: `recovery/enterprise-b00-b04-20261117`, no início
  deste exame em `8f67cb446760fdaa5b2706ed60f6be56c584f72e`.
- Foi criado **outro worktree detached limpo**, a partir desse commit remoto,
  preservando o primeiro worktree e as suas alterações locais. Restauraram-se
  diretamente de `c9a17fd1` os **36 blobs** com manifesto já publicado; todos
  coincidem com seus SHA-1 originais e passam pela análise sintática AST.
- O teste do gate de recuperação (`unittest`) passou com **20 controlos**.
  A suite de integração ainda não foi executada neste ambiente porque falta
  `pytest` e o acesso à distribuição de dependências expirou por timeout.

## Causa verificável da fronteira

| Consumidor/produtor | Confirmação interna observada | Efeito da falha posterior |
| --- | --- | --- |
| `app/xml_service.py::persistir_documento_fiscal` | `db.commit()` após documento e itens | Documento sobrevive a falha nos gates posteriores |
| `registro_analise_service.py::criar_registro_analise` | `db.commit()` após relatório `processando` | Relatório pode sobreviver incompleto |
| `registro_analise_service.py::finalizar_registro_analise` | `db.commit()` após selagem | Resultado selado pode sobreviver ao gate posterior |
| `usage_service.py::incrementar_uso_analise` | `db.commit()` após contadores | Contagem pode sobreviver a operação mal concluída |
| `insights_engine.py::gerar_insights_empresa` | `self.db.commit()` na `main` | Efeito lateral independente, sujeito ao patch I0 pendente |

O circuito original `executar_circuito_enterprise_01` chama o escritor
**antes** dos gates I2/G13/G14/G17/C3–C7. A simples flag opt-in dentro do
escritor não pode desfazer confirmações SQL já realizadas. Uma segunda
selagem posterior também quebraria a proveniência do resultado persistido.

## STOP de autorização, sem correção improvisada

Uma implementação que promete atomicidade **não é segura apenas no ficheiro
`registro_analise_service.py`**. A alternativa de corrigir com `begin_nested`,
interceção/monkeypatch de `db.commit` ou cópia de um segundo escritor
contraria o desenho ratificado e não oferece prova independente.

**STOP_SCOPE_EXPANSION_REQUIRED**: antes de alterar produto, solicitar a Miguel
mandato transacional opt-in que abranja, por intenção e teste:

1. `registro_analise_service.py` — orquestração, reserva e confirmação final;
2. `xml_service.py` — persistência do documento com `flush` sem `commit`
   exclusivamente na modalidade Enterprise isolada;
3. `usage_service.py` — contadores sujeitos ao mesmo limite de transação;
4. `insights_engine.py` — avaliar primeiro o patch histórico `912cb309`
   e impedir confirmação antecipada em modo Enterprise, sem alterar o legado.

O contrato deve conservar a execução **SQLite `:memory:` exclusiva**, exigir
`optante_mei is False`, titular/empresa/NF-e coerentes antes de qualquer
escrita, e recusar publicação/autorização fiscal/checkout. Testes de
identidade, duplicação (chave igual/bytes diferentes), rollback após cada
etapa, retry e produtores do relatório devem passar antes de qualquer
commit de código. Os **25 testes originais B01/B03/B04** e a suite
diferencial de **4.102 casos/13 RED baselined** continuam obrigatórios.

Até decisão expressa: **sem alteração de produto, commit de produto,
merge, deploy ou declaração GLOBAL_GREEN**. Nenhuma alteração em MEI,
motor fiscal, MVA, migrações, SERPRO ou produção foi autorizada.

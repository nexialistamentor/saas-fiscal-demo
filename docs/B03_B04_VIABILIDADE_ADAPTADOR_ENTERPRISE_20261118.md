# SOLVERIS B03/B04 — Parecer de viabilidade da entrada Enterprise exclusiva

**Data:** 18/11/2026. **Natureza:** investigação exclusivamente de leitura sobre o código existente, sem alteração de regras, motor, escritor, MEI, esquema, branches remotos ou deploy.

**Mandato:** Miguel ratificou analisar uma eventual entrada Enterprise `opt-in`, reutilizando componentes existentes, **sem editar** `app/services/registro_analise_service.py` nesta fase. Não ratificou a sua implementação.

**Conclusão:** **não foi demonstrado um adaptador que, apenas compondo a API atual do escritor e mantendo-a intacta, satisfaça simultaneamente a prova documental I2, a selagem antes da publicação e a atomicidade do circuito.** A interface atual exige uma decisão de integração no ponto onde o relatório é produzido e selado, ou uma alteração mais ampla das fronteiras transacionais. **Estado: `CONTRACT_BOUNDARY_UNRESOLVED`, não GREEN.**

## 1. Provas do código, não hipóteses de interface

| Componente | Contrato efetivamente lido | Consequência para adaptador externo |
| --- | --- | --- |
| `app/services/registro_analise_service.py::executar_e_registrar_analise_xml` (`main@a6a2da6c`) | Executa análise, chama persistência XML, insights/score, sela **o resultado XML bruto** e retorna `(relatorio, resultado)` | Não devolve o `DocumentoFiscal` produzido nem injeta `_enterprise_xml_evidence` no resultado selado |
| `app/services/enterprise_i2_documentary_bridge.py::projetar_diagnostico_integral_i2` (`c9a17fd1`) | Lê `verificar_resultado_persistido(rel)`, exige `empresa_id` e `_enterprise_xml_evidence.documento_id` | Sem a prova no payload **persistido e selado**, para em `I2_NO_BOUND_DOCUMENT` |
| `app/services/enterprise_xml_evidence_binding.py` (`c9a17fd1`) | Exige documento, empresa, utilizador, relatório, chave NF-e e SHA-256 correspondente; lê resultado selado para validar o vínculo | Não é correto fabricar vínculo com objeto apenas em memória nem selar só para satisfazer o teste |
| `app/services/resultado_provenance_service.py` (`main`) | `selar_resultado_nao_mei` adiciona envelope; `verificar_resultado_persistido` coteja o fingerprint do JSON persistido | Acrescentar o vínculo depois da selagem sem atualizar a identidade é rejeitado; substituir a selagem já consumada é uma **nova escrita**, não a operação original |
| `app/services/registro_analise_service.py::{criar_registro_analise,finalizar_registro_analise}` (`main`) | Ambos chamam `db.commit()` | O escritor confirma estado em mais de uma transação |
| `app/xml_service.py::persistir_documento_fiscal` (`main`) | Chama `db.flush()` e `db.commit()` antes de devolver `DocumentoFiscal` | O commit documental não é revertido por falha posterior do adaptador |
| `app/services/usage_service.py::incrementar_uso_analise` (`main`) | Chama `db.commit()` | Confirma consumo separadamente |
| `app/services/insights_engine.py` (`main`) | Possui `self.db.commit()`; existe patch pendente `912cb309` de atomicidade | Mesmo que esse patch retire o commit dos insights, os demais commits explícitos permanecem |
| `app/services/registro_analise_service.py` (linhagem `c9a17fd1`) | O escritor original B01/B04 captura o documento, compõe resultado empresarial, insere `_enterprise_xml_evidence` **antes da selagem** e muda o produtor do envelope | Importar toda essa alteração modifica a API **compartilhada**, não apenas o novo circuito |

### Exposição a outras verticais

Chamadores já presentes em `main` para o escritor compartilhado:
`app/main.py` (upload XML), `app/routes/relatorio_router.py` (rotas de relatório), `app/jobs/analysis_job.py`, além de testes do pipeline. Por exemplo, a rota `/gerar-relatorio` aceita `empresa_id` e chama o escritor sem comprovar `optante_mei=False` / regime real antes dessa chamada. O escritor em si também não possui uma guarda de regime. **Não é legítimo presumir isolamento de MEI por nome do módulo.**

### Cuidado adicional com a guarda original

O circuito sintético `executar_circuito_enterprise_01` de `c9a17fd1` exige `sqlite:///:memory:`, titularidade e regime real/presumido. A sua condição `getattr(empresa, "optante_mei", None) is True` **rejeita True, mas aceita `None`**, enquanto `Empresa.optante_mei` é uma coluna nullable em `main`. É uma lacuna de garantia de não-MEI em sentido estrito. Não modificar a guarda sem decisão contratual; qualquer futuro desenho exclusivo deve provar seleção de uma empresa **explicitamente não MEI**.

## 2. Alternativas comparadas

| Alternativa | Faz passar I2/B01? | Atomicidade e exposição | Parecer |
| --- | --- | --- | --- |
| **A. Adaptador externo pós-escrita**: chamar escritor atual, localizar documento por chave/hash, recompor e substituir JSON selado | Em princípio pode construir novo resultado, mas não foi testado | Introduz segunda selagem/escrita após commits do relatório/documento; falha intermediária deixa estado parcial | **Não recomendar** como recuperação soberana |
| **B. Novo escritor Enterprise independente** com cópia da sequência atual | Poderia acomodar a prova antes da selagem | Duplica orquestração, contorna o princípio de reutilização e ainda chama `persistir_documento_fiscal` com commit interno | **Não recomendar** sem missão arquitetural própria |
| **C. Porta `opt-in` no escritor compartilhado**, com predicados explícitos e comportamento padrão preservado | Permite injetar vínculo antes de selar, como na origem B01 | Exige editar módulo compartilhado e validar todas as rotas; não resolve sozinho os demais commits | **Possível candidata a avaliação**, mas fora da autorização atual |
| **D. Separação transacional formal** (primitivas sem commits internos, único commit no limite do caso de uso) | Poderia dar base para uma integração mais forte | Requer alterar `xml_service`, escritor, consumo e possivelmente fixtures; risco transversal | **Outra missão/ratificação**, nunca patch oportunista |
| **E. Manter recuperação como módulos testáveis isolados** | B03/B04 unitários sim; B01/I2 fim a fim não | MEI protegido, mas circuito não operacional | **Único estado atualmente autorizado**, rotulado incompleto |

Não existe prova de que C seja suficiente sem D para toda a atomicidade pretendida. **A frase “adaptador exclusivo seguro” não constitui decisão de arquitetura nem autorização para o construir.**

## 3. Contratos obrigatórios antes de qualquer implementação ratificada

1. Não-MEI inequívoco: empresa, titular, regime e `optante_mei is False`, antes de quaisquer efeitos.
2. Mesmo XML comprovado: chave NF-e, `DocumentoFiscal.conteudo_sha256`, `relatorio.xml_chave`, `empresa_id`, `usuario_id`, itens e fingerprint do resultado.
3. Proibir silenciosamente substituição de documento por mesma chave com bytes diferentes. A `main` atual apanha `DuplicataFiscalError` no escritor sem distinguir o hash; a origem B01 acrescenta esse cotejo. Qualquer mudança é transversal e exige regressão.
4. Resultados I0/I1/I2/G12–G17/B03/B04 sem elevação automática de autoridade fiscal, crédito, pagamento ou competência normativa.
5. Falhas e concorrência antes/depois de cada ponto de confirmação devem deixar rasto explícito, não publicar relatório parcialmente comprovado como válido.
6. Provar contratualmente **inalterados** os chamadores legacy de `/gerar-relatorio`, upload principal, jobs, MEI e os 13 RED preexistentes (sem piora do estado/causa); revalidar os 25 testes obrigatórios de B01+B03+B04.
7. Somente SQLite **em memória** para a execução do circuito original B01; qualquer expansão para PostgreSQL/prod é outra missão. Não tocar Alembic `0060`–`0063` ainda não ratificadas.

## 4. Decisão solicitada a Miguel

**Não implementar A nem B apenas para obter GREEN.** Escolher uma de duas direções, após ler as consequências:

- **Direção 1 — preservar fronteira absoluta (preferível até nova arquitetura):** manter escritor compartilhado intocado; concluir apenas preparação, custódia de blobs e testes isolados, e assumir formalmente B01/B04 como **não integrados**. Poderá ser feito mapeamento B06 documental com aviso de que não se trata de capacidade operacional, mas isso alteraria o pré-requisito da missão B06 e precisa de ratificação.
- **Direção 2 — autorizar uma missão cirúrgica adicional sobre a fronteira compartilhada:** primeiro desenhar e testar o delta mínimo de uma porta `opt-in`/transação sob isolamento não-MEI, com contrato de comportamento antigo intacto e prova de não regressão; implementação só após aprovar os testes e efeitos. Pode exigir tocar na função compartilhada; a atual proibição precisa ser alterada **explicitamente** para essa missão, sem abranger outras mudanças de MEI.

**Sem decisão de Miguel, `GLOBAL_GREEN=false`, `ENTERPRISE_RECOVERY_STATUS=BLOCKED`. Não fazer commit, merge, push, deploy, migração ou avançar para B06 Fase 1.**

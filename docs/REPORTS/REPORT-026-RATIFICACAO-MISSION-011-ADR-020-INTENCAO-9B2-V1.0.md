# REPORT-026 — Ratificação da MISSION-011 — ADR-020 — Intenção 9B2 — RED Diagnóstico — Versão 1.0

## 1. Identificação

- Relatório: REPORT-026
- Missão ratificada: MISSION-011 — ADR-020 — Intenção 9B2 — RED Diagnóstico da Coerência entre NormativeActivation e ActivationGeneration
- Versão do relatório: 1.0
- Natureza: registo documental de ratificação humana

## 2. Estado

RATIFICAÇÃO HUMANA REGISTADA — AGUARDA AUDITORIA, CONGELAMENTO E PUBLICAÇÃO — EXECUÇÃO TÉCNICA AINDA NÃO AUTORIZADA

A ratificação humana foi emitida. Este relatório não autoriza nesta fase a execução técnica do RED.

## 3. Baseline

O baseline publicado declarado para este registo é:

- HEAD: `7e66fac40334720a99ad472d0aa6cd43a6171518`
- origin/main: `7e66fac40334720a99ad472d0aa6cd43a6171518`
- revision PostgreSQL sob diagnóstico futuro: `0039_adr020_gen_exec_decision_fk`

## 4. Identificação e integridade da MISSION-011

- Caminho: `docs/MISSIONS/MISSION-011-ADR-020-INTENCAO-9B2-RED-DIAGNOSTICO-V1.0.md`
- Versão: 1.0
- SHA-256: `88ED6A40C23BF4E5E1BC2BD8764500FFD2A9F02D391518D6947D30E2C3EC361E`
- Tamanho: 13526 bytes
- Estado textual preservado nos bytes: `PROPOSTA — NÃO RATIFICADA — NÃO EXECUTÁVEL`

A MISSION-011 permanece inalterada nos bytes congelados. O seu estado textual não é alterado por este relatório; a ratificação humana é registada externamente no REPORT-026.

## 5. Decisão humana integralmente registada

> RATIFICO a MISSION-011 — ADR-020 — Intenção 9B2 — RED Diagnóstico da Coerência entre NormativeActivation e ActivationGeneration — Versão 1.0, congelada com SHA-256 88ED6A40C23BF4E5E1BC2BD8764500FFD2A9F02D391518D6947D30E2C3EC361E e tamanho de 13526 bytes.
>
> Ratifico que o objectivo exclusivo da futura execução é criar e executar um único RED PostgreSQL que prove que o baseline na revision 0039_adr020_gen_exec_decision_fk aceita uma NormativeActivation cuja decisão exacta difere da decisão exacta da ActivationGeneration associada.
>
> Ratifico o cenário com duas decisões exactas distintas D1/H1 e D2/H2, execução E1 pertencente a D1/H1, geração G1 pertencente a E1 e D1/H1, controlo positivo coerente e NormativeActivation falsa declarando D2/H2 enquanto referencia a geração e a mesma execução pertencentes a D1/H1.
>
> Ratifico que a única falsidade permitida é a divergência entre a decisão declarada por NormativeActivation e a decisão da ActivationGeneration associada. Subject, review, execução, geração, hashes, estados, cardinalidades, bindings e restantes contratos devem permanecer válidos.
>
> Ratifico que a intenção 9B4 permanece separada, posterior e fora do escopo. NormativeActivation e ActivationGeneration devem apontar para a mesma ActivationExecution, sem introduzir divergência de execution_id.
>
> Ratifico que a futura execução técnica poderá modificar somente tests/test_adr020_activation_postgresql.py e criar somente o teste test_normative_activation_rejects_generation_from_different_exact_decision_via_core.
>
> Ratifico que o RED somente será válido quando o controlo positivo persistir e a inserção falsa for aceite pelo banco, fazendo o teste falhar exclusivamente por ausência da DBAPIError esperada, de forma equivalente a DID NOT RAISE DBAPIError.
>
> Após RED válido, o teste deverá permanecer sem correcção e com os seus bytes preservados. Não poderá ser criada migration, alterado app/models.py, seleccionado mecanismo físico ou implementado qualquer GREEN.
>
> Esta ratificação autoriza agora somente a criação, auditoria, congelamento e publicação do relatório de ratificação da MISSION-011.
>
> A execução técnica do RED somente ficará autorizada depois de a MISSION-011 e o respectivo relatório de ratificação serem publicados e HEAD coincidir exactamente com origin/main.
>
> Permanecem proibidos migration 0040, qualquer migration, models, código de aplicação, listener, trigger, constraint, função PostgreSQL, segundo ficheiro técnico, GREEN, 9B4, 9C, 8B2, MIGRATION-BOOTSTRAP-0000-0001, motor ADR-020, gates, endpoints, workers, scheduler, dispatcher, deploy, Railway, produção e docs/ROADMAP_OPS_AGENTES.md.

## 6. Origem da autoridade

A decisão humana é a fonte da ratificação. O REPORT-026 somente regista e delimita essa decisão: não a substitui, não a amplia e não cria autoridade diferente.

Este relatório não inclui hash próprio.

## 7. Objectivo exclusivo ratificado

A futura execução deverá criar e executar um único RED PostgreSQL no baseline `0039_adr020_gen_exec_decision_fk`. O RED deverá provar que o banco aceita uma NormativeActivation cuja decisão exacta difere da decisão exacta da ActivationGeneration associada.

## 8. Cenário RED ratificado

O cenário ratificado é exactamente:

- D1/H1 e D2/H2 válidas e distintas;
- E1 pertence a D1/H1;
- G1 pertence a E1 e D1/H1;
- controlo positivo coerente;
- N_false referencia a geração e a mesma execução pertencentes a D1/H1;
- N_false declara D2/H2;
- subject e review válidos;
- hashes, estados, cardinalidades, bindings e restantes contratos válidos.

## 9. Falsidade única

A única falsidade é: NormativeActivation declara D2/H2 enquanto a ActivationGeneration associada declara D1/H1.

Não existe divergência de `execution_id`. Não se introduz nem se autoriza falsidade própria da intenção 9B4.

## 10. Controlo positivo

O controlo positivo coerente deverá persistir. A sua persistência é condição necessária para que o futuro RED seja considerado válido.

## 11. Separação da intenção 9B4

A intenção 9B4 permanece separada, posterior e fora do escopo. NormativeActivation e ActivationGeneration deverão apontar para a mesma ActivationExecution, sem divergência de `execution_id`.

## 12. Escopo técnico futuro

Quando todas as condições de autorização futura estiverem cumpridas, o único ficheiro técnico que poderá ser modificado é:

`tests/test_adr020_activation_postgresql.py`

Não fica autorizado um segundo ficheiro técnico.

## 13. Nome exacto do teste

O único teste autorizado para a futura execução é:

`test_normative_activation_rejects_generation_from_different_exact_decision_via_core`

## 14. Expectativa RED

O controlo positivo deverá persistir. A inserção falsa deverá ser aceite pelo banco e o teste deverá falhar exclusivamente por ausência da DBAPIError esperada, de forma equivalente a:

```text
Failed: DID NOT RAISE <class 'sqlalchemy.exc.DBAPIError'>
```

## 15. Critérios de validade

Somente será RED válido aquele em que o controlo positivo persista e a inserção falsa seja aceite pelo banco, causando exclusivamente a ausência da DBAPIError esperada.

Não será aceite como RED válido qualquer falha de fixture, comprimento, UNIQUE, FK, subject, review, execução, hash, estado, schema, migration, container ou qualquer falha anterior à inserção falsa.

## 16. Preservação do RED

Após RED válido:

- o teste não será corrigido;
- os bytes do teste serão preservados;
- não será criada migration;
- `app/models.py` não será alterado;
- não será seleccionado mecanismo físico;
- nenhum GREEN será implementado;
- será necessária auditoria read-only;
- será criado relatório separado de encerramento;
- esse encerramento deverá ser congelado e publicado;
- somente depois poderá ser proposta missão GREEN própria.

## 17. Ausência de GREEN

Nenhum GREEN está autorizado por esta ratificação ou por este relatório. Não se selecciona mecanismo físico e não se autoriza qualquer correcção, migration, model, listener, trigger, constraint ou função PostgreSQL.

## 18. Condições para a futura execução

A autoridade executável somente nascerá após a publicação conjunta da MISSION-011 e do REPORT-026. Após essa publicação, HEAD deverá coincidir exactamente com origin/main.

Enquanto ambas as condições não forem integralmente verificadas, a execução técnica do RED permanece não autorizada.

## 19. Actos autorizados agora

Somente estão autorizados agora:

1. criação deste REPORT-026;
2. auditoria documental;
3. congelamento dos bytes;
4. staging manual posterior;
5. commit manual posterior;
6. publicação conjunta da MISSION-011 e do REPORT-026;
7. verificação de HEAD igual a origin/main.

O RED não é declarado autorizado antes dessa publicação integral.

## 20. Actos não autorizados

Não estão autorizados agora:

- criação ou execução do teste;
- pytest;
- containers;
- Alembic;
- migration 0040;
- qualquer migration;
- `app/models.py`;
- código de aplicação;
- listener;
- trigger;
- constraint;
- função PostgreSQL;
- segundo ficheiro técnico;
- GREEN;
- 9B4;
- 9C;
- 8B2;
- MIGRATION-BOOTSTRAP-0000-0001;
- motor ADR-020;
- gates;
- endpoints;
- workers;
- scheduler;
- dispatcher;
- deploy;
- Railway;
- produção;
- `docs/ROADMAP_OPS_AGENTES.md`.

## 21. Intenções e pendências fora do escopo

Permanecem fora do escopo a intenção 9B4, a intenção 9C, a intenção 8B2, MIGRATION-BOOTSTRAP-0000-0001, o motor ADR-020, qualquer mecanismo físico, qualquer GREEN e todas as restantes matérias enumeradas como actos não autorizados.

O encerramento posterior ao RED exigirá auditoria read-only, relatório separado, congelamento e publicação. Uma missão GREEN própria somente poderá ser proposta depois desse encerramento.

## 22. Estado final

A ratificação humana está registada e delimitada. A MISSION-011 permanece inalterada nos bytes congelados. O REPORT-026 aguarda auditoria, congelamento e publicação conjunta com a MISSION-011. A execução técnica ainda não está autorizada.

## 23. Veredicto

RATIFICACAO_MISSION_011_REGISTADA_AGUARDA_PUBLICACAO

# SOLVERIS B02 — exame técnico exato da candidata G5 V3 pós-G4

**Corte:** 31/10/2026, depois da reconciliação física G4 v4. **Natureza:** exame técnico documental pela execução GPT-6 desta conversa; não é auditoria independente, parecer do revisor segregado, assinatura, política ativa nem R7 final. Não houve consulta SQL direta, testes novos ou alteração de autoridade.

## Objeto examinado

- Ficheiro: `POLICY_G5_CANDIDATO_SUCESSOR_V3_PARA_REVISAO.json`
- SHA-256 exato: `32068cadf7297fb5958af25650899abffc667c17f3508f9261a165b8dfbd5fc7`
- Hash SHA-256 apenas do corpo técnico *provisório* em JSON canónico (chaves ordenadas): `87ea43c09e6315da44c2b8bd36dc35345da0a05452b11a35f757ab741f80b868`
- Fonte histórica V2: blob `87dd0560d842f8b9f20d808363496fa60786710c`; G5 V1/V2 não editados.
- Script materializador ratificado: `tools/b02_g5_v3_temporal_materialize_candidate.py`, blob `e658a51bd9f4876cd2ffa2ec2b233b092f86f60b`
- G4 v4: `B02-05ede-activation-v4`, hash `cf617e146b3451555898d8253fba8bb13dfa6ff99776b50978e0ba68df4cb482`; recebidos do executor Windows na saída `G4_V4_PHYSICAL_RECONCILED_G5_V3_DRAFT_ONLY`. Esta execução não teve acesso direto ao PostgreSQL.
- Janela previamente ratificada `B02-G4-G5-TEMP-SUCCESSOR-20261031-01`: `2026-11-01T00:00:00Z` a `2026-11-15T00:00:00Z` (fim exclusivo).

## Confronto do conteúdo canónico candidato

**PASS de estrutura declarada:** `policy_version=3`, `policy_id=SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE`; ambos os documentos C3 preservados exatamente, Res. 571/2019 SHA256 `af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d` e Res. 1245/2025 SHA256 `e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832`. Os seis IDs operacionais de cada documento usam sufixo V3, sem reuso V1. Ambos os vínculos G4 apontam ao ID V4 e ao hash real acima; as oito datas temporais obedecem à janela aprovada. A referência da 0064 candidata usa SHA256 `7a42f583a4ca604a697a2e9a11cda7ffdb88d92c40bfbd181e408da736293074`.

**Ainda incompleto por desenho do fail-closed:** raiz `capability_root_id=null`, actor de release `null`, revisor V3 `null`, adoção V3 `null`; `institutional_evidence_bindings={}`. Cada documento tem `g4.origin_report_binding=null`, `g4.verifier=null`, `g4.outcome=AWAITING_OWN_CURRENT_FOUNDER_ORIGIN`; cada sanitização tem `outcome=AWAITING_CURRENT_REAL_INDEPENDENT_INSPECTION` e manifestos não completos. O mecanismo não autoriza instalação, operação ou seleção fiscal.

## Decisão solicitada, sem duplicar o pedido anterior

À execução revisora G5 V3 própria, com identificação/conflitos segregados: **emitir avaliação própria da admissibilidade exata deste ficheiro** e apontar exclusivamente correções concretas. A emissão de `auditada_favoravelmente` e ratificação final depende do **corpo canónico definitivo pós-preenchimento de raiz, origem e inspeção** e de decisões com seus hashes, não do hash técnico provisório `87ea43...`. O parecer final histórico V2 não é condição predecessora (ratificação de substituição já existente).

Ao custódio nativo: fornecer raiz/assinatura V3 com proveniência real, header e SHA256 exatos para o builder PG17.10 Trixie já existente. Ao executor fiscal: reutilizar os PDF C3 e excertos já custodiados, vinculando depois `NormativeArtifact → ExtractionResult → RuleVersion → item fiscal real` mediante execução competente, sem novo download e sem suposições de regras fiscais.

**Conclusão:** `V3_EXACT_DRAFT_STATIC_CONSISTENT_BUT_NOT_AUTHORIZABLE`. G4 temporal resolvida no âmbito do resultado do executor; G5 institucional, raiz, 0064/0065 físicas, duas unidades reais, R6 por item e R7 final não são inferidos. Preservar R4/R5/ACL/JSONB/0065 sintético e os atos V1/V2 históricos.

## Impedimento técnico confirmado — raíz de autenticação de origem NÃO provisionada

A inspeção da fonte do verificador atual encontrou três registos fechados por definição, sem nenhum valor proveniente de utilizador, ambiente ou bundle admitido como raiz:

- `app/services/enterprise_b02_founder_runtime.py` (blob Git `700ab498717f3e3809aea9342bde0e119ea8d4ca`): `_RUNTIME_AUTHORIZATIONS=MappingProxyType({})`; rejeição explícita `RUNTIME_AUTHORIZATION_MISSING_OR_AMBIGUOUS`.
- `app/services/enterprise_b02_founder_review_profile.py` (blob Git `274a194c68686340e243ede408cc0ba58450bf15`): `_AUTHORIZED_CONTEXTS = MappingProxyType({})`.
- `app/services/enterprise_b02_institutional_verifier.py` (blob Git `6990e1afe918c7c9ebd2f5745c75b04506ece89d`): `_TRUST_ROOTS = MappingProxyType({})`; rejeição explícita `REAL_INSTITUTIONAL_TRUST_ANCHOR_MISSING`.

O verificador `verify_document_authenticity_with_founder_runtime` executa `_root(subject,now)` antes de aceitar a origem dos bytes; com o mapa vazio, a resposta real não pode ser `conclusivo_favoravel`. Isto **não invalida** G4 v4 reconciliada, os PDFs C3, o exame estático A2 nem os ensaios sintéticos. Explica precisamente por que as duas comprovações reais `FOUNDER_ORIGIN` ainda não podem ser produzidas mediante simples chamada ao código.

**Ato externo exato e único para a autoridade/custódio:** vincular uma execução reconhecida ao sujeito G4 documental e à ativação física `B02-05ede-activation-v4` hash `cf617e146b3451555898d8253fba8bb13dfa6ff99776b50978e0ba68df4cb482`; emitir/assinar a raiz e os vínculos de aceitação, mandato e relatório de origem próprios para os dois PDFs C3, com vigência e papéis segregados. Só depois um deployment **expressamente autorizado**, com revisão de identidade/provenance, pode provisionar os registos pertinentes e permitir a inspeção real. Não aceitar `synthetic_only=true`, não usar chaves legadas V1/V2, não ler raízes de payloads, não alterar as tabelas protegidas por atalho.

**Conclusão técnica do gate:** `G4_V4_PHYSICAL_PASS_BUT_G4_ORIGIN_ROOT_UNPROVISIONED`; nenhuma instalação, assinatura ou auditoria final inferida. A ordem operacional correta permanece: custódia/autoridade real → inspeções FOUNDER_ORIGIN verificadas → política G5 V3 própria → raiz/ELF nativos → 0064/0065 e duas unidades reais → R6/R7.

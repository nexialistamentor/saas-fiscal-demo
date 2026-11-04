# SOLVERIS B02 — Delta único: seleção da adoção aplicável ao assinador V2

**Âmbito exclusivo:** resolução da ressalva apontada nos aditamentos ORIGIN publicados no commit `d1f6cadc66b8cf5daace7c6b313cfbc3c11f905d`. Não revoga nem reescreve pareceres, decisões, ORIGIN, G4, R4, A2, sete JSON ou 149 provas. Esta execução foi **autora/integradora**, não revisora segregada.

## 1. Defeito e correção implementada

Anteriormente `_source_pinned_signer_authority()` contava todos os comentários JSON com o mesmo `schema`/`id` e exigia cardinalidade 1. O ato OWNER histórico, emitido em `2026-11-04T00:04:33Z` e publicado em [PR #28, comentário 6618713028](https://github.com/nexialistamentor/saas-fiscal-demo/pull/28#issuecomment-6618713028), refere-se ao signer `b8ff97373476bb3ef1b34362612eedd014f0ff21`. A existência legítima deste ato não pode bloquear, por contagem global, uma adoção posterior e distinta do código corrigido.

**Código corrigido:** `tools/b02_documentary_signer_v2.py`, Git blob **`f1e866ba31d02a5e6c7f99c80d1e9833a9a0bbc2`**, PR #28, commit `2b9ed440d27599e9bdd1eeaab8e70605a79914ae`. O seletor deriva o blob relevante dos **bytes do próprio ficheiro Python em execução** (`git_blob(Path(__file__).read_bytes())`); não aceita escolha por CLI, por ordem dos comentários ou por corpo local. Somente atos OWNER canónicos com esquema/ID e **blob do assinador atual** entram na cardinalidade. O ato histórico fica preservado mas não se torna adoção aplicável para código diferente.

Se houver **zero** atos OWNER aplicáveis ou **mais de um** (ainda que conflitantes ou revogados), a execução provoca STOP. Havendo um, compara **bytes exatos** ao ficheiro local, exige fonte imutável `created_at==updated_at`, owner ID/login/associação OWNER e URL da PR #28, issuer Miguel, política/escopo, SHA-256 fixos da decisão e manifesto, aprovação/signing, não-revogação, limites sem autoridade operacional e datas UTC. Verifica `issued_at <= created_at <= valid_from < valid_until`, dentro da janela preexistente. Os restantes gates de `validate()` e revalidações TOCTOU mantêm os controlos de mandatos, revisão, contemporaneidade e instante efetivo.

**Fonte OWNER presente, verificada:** existe atualmente **uma única adoção antiga**, comentário `6618713028`, para `b8ff9737...`; **nenhuma adoção OWNER efetivamente emitida** para o novo signer `f1e866ba...`. Não escolher a antiga para assinatura.

## 2. Pins finais propagados nas PRs existentes

| Componente | Git blob aplicável | Referência |
| --- | --- | --- |
| Validador ORIGIN V2 (intacto nesta alteração) | `31be879d8d0fab9c572916b67f66ee32037b3495` | PR #27 |
| Assinador V2, seletor corrigido | `f1e866ba31d02a5e6c7f99c80d1e9833a9a0bbc2` | PR #28, `2b9ed440d27599e9bdd1eeaab8e70605a79914ae` |
| Testes novos de seleção | `aa46a1fde39a96c99ea01a30d4f74453c46bd496` | PR #28, `tests/test_b02_signer_v2_applicable_adoption.py` |
| Consumidor V2 | `968ed38d73dee868dedd40362238564c111adbce` | PR #29, `app/services/enterprise_b02_authorized_trust_v2.py` |
| Testes de compatibilidade repinados | `489972cbbe80f50fd1df80c5a9aec0637be2af6c` | PR #29 |
| Windows, procedimento já existente | `dcb2db9f30556ec03c7628c41b020849506f0049` | PR #28, `tools/B02_SIGNER_V2_WINDOWS_APOS_REVISAO_E_ADOCAO.ps1` |
| Projeção R7 somente leitura | `b4a8a3557e3c5c63048c28ac69ccf2fba64d3cae` | PR #27 |
| Minuta não eficaz, sem aprovação nem parecer inventados | `97caae558071d259128d543919741f8b78ca98ae` | PR #27, `evidence/b02/SOLVERIS_B02_SIGNER_V2_ADOCAO_ESPECIFICA_MINUTA_NAO_EFICAZ.json` |

**Procedimento Windows:** Git blob `dcb2db9f30556ec03c7628c41b020849506f0049`; SHA-256 integral do ficheiro `b78dae402ee5f769116b8a1a98e6ce898ac47d7ac82f33e92fbec80e2f2e7dad`. Confere signer `f1e866...` contra commit de origem `2b9ed440...`; não foi executado no Windows.

A adoção específica **já emitida** `SOLVERIS_B02_SIGNER_V2_ADOCAO_ESPECIFICA_EMITIDA_20261104.json`, SHA-256 `b3e643d3622835e65f28ce404dbdb47ea6b4ab15be51f4206f21095f32959261`, permanece imutável e é **exclusiva do signer anterior** `b8ff9737...`. A minuta não eficaz está vinculada ao novo signer, mas continua `approved=false`, `signing_authorized=false`, `review.outcome=null` e sem data de emissão; não substitui ato competente.

## 3. Verificações novas e preflight integrado

Execução isolada do código exato extraído das PRs, Python 3.14, pytest e cryptography:

- **14 PASS** — coexistência histórico/aplicável, ordem inversa dos comentários, outro signer, outros bytes da decisão, dupla adoção aplicável conflitante, revogado, proprietário indevido / ID / associação / comentário alterado, datas inválidas, corpo local divergente. Nenhum hash da CLI escolhe autoridade.
- **3 PASS** — proteção TOCTOU já existente no signer, após a correção de seleção.
- **5 PASS** — consumidor completo com pin repinado, **17 testes fora do escopo não executados**.
- **Total focal: 22 PASS**, `exit code 0`; resultados sintéticos não equivalem a revisão competente.

**Preflight com dados reais (sem assinatura):** `7/7` JSON reais e intocados, exatamente 149 provas. Manifesto SHA-256 **`99d1a424015fc03a5ece71e84341eee748fd0b2fc1bebd238f9df2ede253a6c1`**. `decision.json` reproduzido byte a byte: **1.118 bytes**, SHA-256 **`d3602168c53debd10421aa83d1e980c632870b660be18a451d5b5a3d998c6520`**. Continuidade ORIGIN V2 final `continuity_v2_conditions_met`. O signer corrigido `validate()` sobre os sete JSON reais e os **bytes originais autorizados** deu PASS, utilizando **chave pública e adoção OWNER de ensaio**; teste de seleção coexistente utilizou comentário histórico real como corpo de referência mais comentário novo SIMULADO, e não promoveu autoridade.

**Consumidor:** `_v2_validate_exact()` com os **mesmos sete JSON reais**, validador de continuidade verdadeiro e assinatura Ed25519/ROOT/parecer/adoções estritamente **SINTÉTICOS** (apenas em `/tmp`) devolveu `V2_SIGNED_CUSTODY_VALIDATED_NOT_RUNTIME_PROVISIONED`; `runtime_provisioned=false`, `sql_writes=0`, `fiscal_authority=false`. Para permitir a chave sintética, o **decision.json de ensaio do consumidor** diferiu no fingerprint do original; **não é** assinatura dos 1.118 bytes autorizados. Este limite é explícito e não representa implantação física.

**R7 read-only no HEAD `372b3509f604731d442f38a51fa352afa992a62d` da PR #27:** `B02_R7_V2_READONLY_RECONCILED_NO_RELEASE`, `status=B02_OPEN_B03_BLOCKED`, `protected_writes=0`, `r7_closed=false`. Nenhum dos sete JSON ou das 149 provas foi alterado, nem foram executadas assinaturas reais, comandos Windows, SQL ou G5.

## 4. Única sequência institucional restante — não presumir atos

1. **Revisor novo e funcionalmente elegível:** aprecia somente o delta final do seletor `f1e866...` e o consumidor `968ed...` com as provas acima. Declara identificação, aceitação do mandato, participação real, conflitos, limites e conclusão própria; emite os ficheiros de revisão canónicos e SHA-256 efetivo. Os aditamentos do autor publicados em `pareceres_publicados_20261104` **não** são revisão segregada. Esta execução participou na implementação e não pode aprovar o próprio código.
2. **Miguel, somente após parecer competente:** adoção específica **prospectiva do NOVO blob do assinador**, vinculando o parecer real pelo SHA-256, emissão UTC e eficácia verdadeiras, confirmação atual de não revogação. O corpo canónico aplicável deverá ser emitido pelo OWNER na PR #28 e consumido como `SIGNER_AUTHORITY.json`. Conservar o ato histórico e a autorização dos mesmos 1.118 bytes; não solicitar nova ratificação genérica. **Janela original imutável:** `[2026-11-03T18:00:00Z, 2026-11-04T18:00:00Z)` — qualquer adoção posterior ou execução fora dela provoca STOP, nunca retroagir.
3. **Só após atos eficazes e conferidos:** o executor Windows competente verifica hash e fonte do procedimento já existente, consome o parecer/adoção exatos, a custódia local e assinatura física sem transmitir a chave; readback matemático, confiança e mecanismos já previstos, seguidos de provas operacionais e decisão R7 própria. Não repetir ORIGIN, recolhas físicas, G4, R4, A2, certificados ou suites históricas. Não declarar `B02 CLOSED` sem reconciliação operacional mais decisão R7.

**Estado desta entrega: DELTA_TECNICO_CORRIGIDO_COM_PROVAS; AUTORIDADE_NOVA_NAO_EMITIDA; R7_NO_RELEASE.**

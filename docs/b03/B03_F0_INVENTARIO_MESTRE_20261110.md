# SOLVERIS Enterprise — B03: fonte única de continuidade, inventário e anticópias

**Corte verificável:** GitHub commit `f7825ecdd90f1da5cfb07fe8c594afd1e38637e6` (R7/B02 CLOSED, 09/11/2026). **Branch deste documento:** `b03/inventario-antidup-20261110`. **Estado:** F0 auditoria estática do remoto; nenhum teste, deploy, SQL ou mutação dos motores foi executado nesta análise. **Não declarar** que modificações locais ainda não commitadas estejam neste documento: o GitHub não as recebe automaticamente.

## Decisão e fronteiras

1. **B00 e B01 CLOSED; B02 CLOSED com ressalva fiscal real**: preservar os âmbitos já ratificados. O R7 está em `evidence/b02/r7/B02_R7_CLOSED_20261109.md`, R6 sintético em `evidence/b02/r6/B02_R6_SYNTHETIC_CLOSURE_20261109.md`; B02 não é B03.
2. **Não criar novo motor fiscal/comparador/orquestrador nem novas migrations por antecipação.** Detectado motor e circuito B01 existentes que já executam parte substancial do B03.
3. **B03 é genérico por jurisdição desde o contrato**, não “PR hardcoded”. A primeira prova usa os dois documentos PR reais do B02, mas exige NF-e/sujeito/operação/regra compatíveis; dois PDFs não provam por si só um caso de ICMS-ST.
4. **Sem cadeias institucionais G5 copiadas para B03**: código+testes+proveniência+auditoria focada, respeitando a autoridade vigente. Não remover fail-closed dos componentes antigos.
5. **Produtos/tributos**: o B03 compara diferenças numéricas; não transforma valor divergente em crédito fiscal recuperável sem escritura, recolhimento e os fundamentos aplicáveis.
6. **Segurança**: não fazer push automático de alterações desconhecidas do Windows, ficheiros `.env`, credenciais ou chaves privadas. O auditor não deve executar a aplicação nem SQL.

## Mapa de fontes existentes — um dono por função

| Necessidade | Código já existente | Condição atual |
|---|---|---|
| Parser XML NF-e | `app/xml_service.py`, `app/services/document_ingestion/xml_fiscal_adapter.py`, `classifier.py` | Não criar parser B03 |
| Motor base ST, ICMS próprio e ICMS-ST | `app/motor_fiscal.py::MotorFiscal` | Matemática existente; usa float/round |
| Comparação por item | `app/services/tax_consistency/tax_consistency_engine.py::TaxConsistencyEngine.verificar_consistencia` | BASE_ST + ICMS_ST, tolerância R$0,01, sem autoridade jurídica |
| Regras MVA/PMPF | `app/services/tabela_normativa_service.py::buscar_mva`, `resolver_base_calculo_st`, `verificar_cobertura_normativa_st` | Seleção simplificada UF+NCM+data; não decide CEST/CFOP/regime |
| Resolvedor de parâmetros | `app/services/fiscal_utils.py::resolver_aliquota_e_mva` | Bloqueio sem norma; valores fallback sem autorização |
| G12 | `app/services/enterprise_g12_st_item_reconciliation.py::confrontar_st_por_item_g12` | Já chama parser, regra, motor e G1; só saída interna ICMS10/modBCST=4, sem acessórios ou redução |
| G13 | `app/services/enterprise_g13_subject_st_bridge.py` | Vincula empresa, usuário, relatório, item e hash |
| G14 | `app/services/enterprise_g14_operational_normative_scope.py` | 27 UFs; confronto NCM, CEST, CFOP, CST, regime, vigência; só operação interna |
| G15–G18 | `app/services/enterprise_g15_adr020_primary_artifact_link.py`; `enterprise_g16_temporal_rule_chain.py`; `enterprise_g17_publication_coverage_checkpoint.py`; `enterprise_g18_external_publication.py` | Artefacto, extração, RuleVersion, alterações, cobertura; não provam revogação/vigência legal exaustiva |
| Vínculo normativo B02 | `app/services/enterprise_b02_normative_binding.py` | Cotejo read-only C1/C3–C6, TabelaMVA, ExtractionResult e RuleVersion; B02 não se altera |
| C3 seleção normativa | `tools/enterprise_g113_temporal_mva_evidence.py` | Extrai candidato temporal de PDFs autenticados por bytes, não decisão fiscal |
| C4 confronto | `tools/enterprise_g113_c4_fiscal_item_bridge.py` | Confronta item, G12/G13/G14/G1 e C3; não duplica cálculo |
| C5 parâmetros | `tools/enterprise_g113_c5_parameter_trace.py` | Rastro MVA/alíquota/base/ST calculados; compara candidata documental |
| C6 proveniência | `tools/enterprise_g113_c6_l2_record_provenance.py` | Identifica linha L2; não prova unicidade/CEST por si |
| C7 dossiê | `tools/enterprise_g113_c7_diagnostic_dossier.py` | Dossiê interno de C3–C6, sem afirmação de crédito |
| Circuito B01 | `app/services/registro_analise_service.py::executar_circuito_enterprise_01` | **Já liga I2, G13, G14, G17, C3–C7 e I0. SOMENTE SQLite em memória, sintético, não publicável** |
| Projeção completa | `app/services/enterprise_integral_projection.py` | I0 enumera 52 capacidades; não presume execução de todas |
| Autenticidade NF-e | `app/services/enterprise_nfe_i5_observation_link.py`, `enterprise_nfe_i7_xml_signature.py`, `enterprise_nfe_i8_signer_identity.py`, `enterprise_nfe_i9_chain_anchor.py`; I10–I12 | Reutilizar; não replicar assinatura/custódia |

**Árvore observada:** 54 ficheiros `app/services/enterprise_*` e 8 `tools/enterprise_*` no commit fixado. Nomes não provam execução em produção.

## Testes existentes — inspeção de definições (não reexecutados)

- G12: `tests/test_enterprise_g12_st_item_readonly.py` — 24 testes, casos de XML, regra, PMPF, expiração, ICMS próprio, inter-UF e XXE.
- G14: `tests/test_enterprise_g14_operational_normative_scope.py` — 28, UF/CEST/NCM/CFOP/CST/regime/vigência, proprietário, duplicação.
- C4: `tests/test_enterprise_g113_c4_fiscal_item_bridge.py` — 32, comparação numérica por item e isolamento de identidades.
- C5: `tests/test_enterprise_g113_c5_parameter_trace.py` — 32, parâmetros, aritmética e divergência MVA.
- C6: `tests/test_enterprise_g113_c6_l2_record_provenance.py` — 25, fonte, data, registo e prova negativa.
- G16: `tests/test_enterprise_g16_temporal_rule_chain.py` — 36, ativação, regra, relação, revisão e revogação declarada.
- B02 normativo: `tests/test_enterprise_b02_normative_binding.py` — 42, ligação exata, aplicabilidade e duplicados L2.
- G1: `tests/test_enterprise_g1_consistencia_causal_item.py` — 22, comparação/correspondência e fail-closed.

**Total:** 241 definições de testes inspecionadas nessas oito classes. Não equivalem a 241 PASS nesta auditoria; utilizar os resultados históricos já aceites e reexecutar só deltas.

## Lacunas concretas e ordem de trabalho

**F0 — Prevenir duplicidade, antes de editar:**
- Utilizar a ferramenta `tools/b03_auditoria_antidup_readonly.py` sobre o worktree local de trabalho e sobre mudanças não commitadas. Ela não importa os módulos da aplicação, não liga à rede nem escreve.
- Executar `tools/B03_CAPTURAR_WIP_LOCAL.ps1` para listar todos os worktrees Git locais e gerar inventário JSON de ficheiros modificados, staged, untracked e eliminados. Inventário não equivale a backup dos bytes.
- Classificar cada proposta: `reutilizar`, `estender mínimo`, `não tocar`, `sem prova`. Guardar proprietários acima como fonte canónica.

**F1 — Contrato/gov leve, sem schema paralelo:**
- `JurisdictionContext`: esfera (federal/estadual/municipal), UF origem, UF destino, território da norma, data da operação, natureza/modalidade, regime, NCM, CEST, CFOP, CST/CSOSN, método e `RuleVersion`/artefacto. É contrato de entrada, **não nova base de dados**.
- Separar `jurisdição declarada`, `cobertura da regra na operação` e `prova jurídica`; falta de correspondência → `COBERTURA_NAO_COMPROVADA`, nunca aplicar PR em PA apenas porque NCM coincide.
- Governança: Git, prova/relatório de execução e testes focais; sem reconstituir G5.

**F2 — Delta de código mínimo:**
- Reutilizar `MotorFiscal` + `TaxConsistencyEngine` + G12/G13/G14/G16 + C3–C7. Só construir um **adaptador fino**, se comprovado que o contrato existente não aceita jurisdição, contexto e resultados de execução real.
- Não mexer no `executar_circuito_enterprise_01` para remover a guarda SQLite. Separar uso real com entrada controlada, sem outro motor.
- Regra ausente, ambígua, expirada ou incompatível → abstenção, não fallback fiscal autorizado. Considerar frete, seguro, descontos, redução base, operação interestadual e ICMS próprio **somente quando sustentados por implementação e teste**.

**F3 — Validação focal:**
- PR: dois PDFs R5 documentais identificados e persistidos na base real; XML sintético PR prova somente cálculo/cadeia interna. Uma NF-e real elegível para esses NCMs continua pendente conforme R7.
- Negativos: PR aplicado indevidamente a PA, CEST/CFOP/CST/regime/data divergente, regra duplicada/expirada, ausência de regra, valores por item trocados, arredondamento R$0,01, empresa divergente, não promover crédito/checkout.
- Usar mesmos hashes e identidades nos resultados C5/C6/C7; não repetir testes antigos sem alteração causal.

**F4 — Fecho B03 delimitado:**
- Evidência de cálculo por item + proveniência + jurisdição + estados de abstenção + execução integrada no âmbito demonstrado + ensaio de regressão mínimo.
- Primeiro caso normativo PR não implica “nacional comprovado”; a estrutura deve aceitar novas UFs sem editar fórmula nem hardcode. B03 técnico fechado ≠ recuperação fiscal comprovada ≠ oferta comercial habilitada.
- Um commit/PR de delta mínimo, revisão e push explicitamente autorizados. Preservar B00/B01/B02.

## Verificação de duplicidade e erros anteriores

- **Não criar** `motor_fiscal_v2`, `comparador_b03_alternativo`, `resolver_mva_novo`, duplicar `ENGINE_REGISTRY` ou pipeline C3–C7.
- `buscar_mva` usa `.first()` após priorizar fonte/versão; sozinho não prova unicidade nem enquadramento jurídico completo. O B02 já tem guarda de duplicidade L2 para o próprio âmbito.
- G12 calcula ST usando `vICMS` de XML, não ICMS próprio independentemente demonstrado; C5 inspeciona parâmetros executados, não certifica direito a crédito.
- G14 restringe NF-e modelo 55, saída interna, CFOP 5xxx e regime `real/presumido`; a ampliação nacional é por novas modalidades, não por apagar negativas.
- Não colocar ficheiros apenas em `$env:TEMP`; propostas de mudança devem ter um destino Git controlado e leitura de retorno.

## Recursos e comando de localização

**Branch documental:** `b03/inventario-antidup-20261110`. **GitHub:** https://github.com/nexialistamentor/saas-fiscal-demo/tree/b03/inventario-antidup-20261110/docs/b03

Para localizar este ficheiro de qualquer checkout com `origin` correto:

```powershell
git fetch origin b03/inventario-antidup-20261110
git show FETCH_HEAD:docs/b03/B03_F0_INVENTARIO_MESTRE_20261110.md
```

A auditoria local é separada: alterações ainda só no Windows não são visíveis no GitHub. `tools/B03_CAPTURAR_WIP_LOCAL.ps1` cria inventário físico com nome/status/hash e não envia conteúdos; após revisão, preservar fontes locais específicas por commit de trabalho próprio (não misturar com o encerramento B02; não enviar segredos ou chaves). Sem ver o WIP, é incorreto declarar que os seus bytes estão no remoto.


## Adenda F0 — Auditoria dos snapshots Windows de 10/11/2026 (log recebido)

O comando antigo `tools/B03_CAPTURAR_WIP_LOCAL.ps1` produziu um inventário em
`%LOCALAPPDATA%\\SOLVERIS\\B03\\B03_LOCAL_WORKTREES_20261110T230734Z.json`
mas não realizou a captura completa: **22 worktrees** reportados, **10 snapshots
Git locais**, **11 sem diferenças detetadas** e **1 interrompido**:
`C:/dev/saas-fiscal-demo-mei` (65 ficheiros de status, 2 alertas).
A contagem total reportada foi 188 entradas de status, não 188 ficheiros necessariamente preservados.

O antigo script chamava `git add -A` num índice temporário, incluindo ficheiros
fora do filtro analisado. O log revelou muitos avisos CRLF em
`venv311/Lib/site-packages`. **Avisos não são prova de inclusão**, mas exigem
inspeção das árvores Git reais dos snapshots antes de qualquer push.
Não executar novamente a versão anterior nem publicar `b03/wip-local-*`
automaticamente. Não apagar refs locais nem limpar diretórios.

Os snapshots registados nos logs (somente locais, não publicados):
- `b03/wip-local-20261110T230734Z-3` — `C:/dev/saas-fiscal-demo`.
- `b03/wip-local-20261110T230734Z-4` — `C:/dev/saas-fiscal-demo-a1`.
- `b03/wip-local-20261110T230734Z-8` — `C:/dev/solveris-b02-g5-v5-publicacao`.
- `b03/wip-local-20261110T230734Z-13`, `-14`, `-16`, `-17`, `-18`, `-20`, `-21` — worktrees `solveris-mei-*`.

A ferramenta `tools/B03_CAPTURAR_WIP_LOCAL.ps1` foi substituída no Git por
**V2 somente leitura**: descobre worktrees/clones Git no diretório base e
em `-AdditionalRoots`, lista `git status`, caminhos ignorados e refs locais,
gera JSON em `%LOCALAPPDATA%\\SOLVERIS\\B03`. **Não cria snapshots,
commits, índices temporários nem faz push.** Ficheiros não versionados fora
das raízes informadas não são descobertos; mesmo o JSON completo não é
um backup de bytes. A próxima seleção de fontes para commit/push será
precedida de auditoria dos paths e da presença de segredos; B02/MEI
não serão alterados para desenvolver B03.


## Adenda F0 — 2.ª leitura física Windows (10/11/2026 às 23:18 UTC)

**Origem:** saída textual enviada por Miguel do comando de auditoria V2; o JSON local
`C:\Users\Oem\AppData\Local\SOLVERIS\B03\B03_INVENTARIO_COMPLETO_20261110T231811Z.json`
não foi recebido neste ambiente. Os totais abaixo contam entradas `git status`
e caminhos ignorados reportados; não provam bytes preservados.

- 24 worktrees, **189 entradas WIP** e **1000 entradas ignoradas**.
- `B03_DISCOVERY_WARNINGS=0` apenas para raízes e worktrees encontrados; não
  prova cobertura de diretórios externos nem de código em pastas ignoradas.
- `SNAPSHOT_REFS=0` em todas as linhas é **falso negativo do leitor V2**:
  `for-each-ref refs/heads/b03/wip-local-` não corresponde a componentes
  de nome maiores. Corrigido no script publicado para listar `refs/heads/b03`
  e filtrar `b03/wip-local-*`. As refs físicas continuam por verificar.
- `.pytest_cache/` deu aviso de permissão no worktree MEI. Não forçar ACL,
  não apagar cache nem silenciar como prova de completude.
- As refs locais anteriores NÃO foram enviadas ao GitHub; os ambientes
  `venv311` podem ter entrado em alguns snapshots por causa do antigo
  `git add -A`: qualquer push depende da inspeção das árvores.
- O script atual é **somente leitura**: mostra refs, conta candidatos fonte
  ignorados (`app/tools/tests/docs/migrations/scripts/frontend-dashboard/src/native`)
  e classifica ambientes/dependências separadamente.

| Worktree | WIP | Ignorados |
|---|---:|---:|
| `atlas/brigade-l3-clean` | 0 | 28 |
| `atlas/verify-0044` | 0 | 22 |
| `saas-fiscal-demo` | 13 | 480 |
| `saas-fiscal-demo-a1` | 81 | 30 |
| `saas-fiscal-demo-mei` | 65 | 281 |
| `saas-fiscal-demo-mei-route-release` | 0 | 6 |
| `saas-fiscal-railpack-proof` | 0 | 2 |
| `solveris-b02-g5-v5-publicacao` | 21 | 25 |
| `solveris-b02-v12-safe-20261109_152537` | 0 | 3 |
| `solveris-mei-composicao-consultiva-v1` | 0 | 20 |
| `solveris-mei-das-diagnostico` | 0 | 14 |
| `solveris-mei-das-pdf-lista` | 0 | 14 |
| `solveris-mei-preview-4b4514a` | 1 | 1 |
| `solveris-mei-preview-7821072` | 1 | 1 |
| `solveris-mei-receitas-informadas` | 0 | 19 |
| `solveris-mei-release-32d16b1` | 2 | 1 |
| `solveris-mei-release-4334fad` | 1 | 16 |
| `solveris-mei-release-4ab1262` | 1 | 1 |
| `solveris-mei-release-b1e114b` | 0 | 0 |
| `solveris-mei-release-b24a9ef` | 1 | 15 |
| `solveris-mei-release-fe912d7` | 2 | 1 |
| `solveris-mei-retirada-abertura` | 0 | 16 |
| `solveris-vercel-release-83ce80a` | 0 | 1 |
| `solveris-vercel-release-fd6a16a` | 0 | 3 |
| **TOTAL** | **189** | **1000** |

**Próxima decisão:** obter o JSON local ou a saída focal das refs corrigidas;
distinguir source code não commitado, dependências, dados normativos e
artefactos sensíveis; deduplicar contra HEAD remoto. Nenhum novo motor B03
ou migração SQL autorizados a partir desta contagem.

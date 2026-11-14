# SOLVERIS — Fase 4 / Etapa 3
## Proposta de escritor ADR-020 segregado do B02 — apenas análise arquitetural

**Data:** 13/11/2026
**Repositório:** `nexialistamentor/saas-fiscal-demo`
**Branch examinada:** `cobertura-nacional-jurisdicoes-fase4-cest-remetente`
**HEAD observado:** `8e8b72c855f07d322b359c7a198fb34d5348724e`
**Estado:** **PROPOSTA NÃO RATIFICADA PARA IMPLEMENTAÇÃO**. Nenhum código, migração, registo, teste de escrita ou conexão de gravação foi criado nesta missão.

### 1. Decisão proposta

**Recomendo um novo serviço operacional ADR-020 de custódia documental, com sessão PostgreSQL explícita e segregada, sem chamar nem alterar `stage_completion`.** O primeiro objeto de negócio atendido seria somente **PA / NCM `22021000` / CEST `0301001` / categoria `distribuidor_deposito_atacadista`**, dividido em duas versões históricas candidatas: V1 (Decreto 2.588/2022, 30/08/2022–15/03/2023) e V2 (Decreto 2.931/2023, início em 16/03/2023; termo e continuidade sujeitos à verificação de atos posteriores). Não há autorização de cálculo nem de inserção.

**Condicionante decisiva:** as execuções concluídas de aquisição e extração **não são invenções do B02**. São predecessores obrigatórios do ADR-020 fundacional. Um escritor fora do B02 pode ter *as suas próprias execuções e evidências reais*, mas **não pode prescindir delas** nem preencher estados `concluida` fictícios. A viabilidade do escritor com a versão de esquema efetivamente selecionada ainda precisa de prova em ambiente descartável, especialmente quanto aos gates de sanitização de `0025` e aos gatilhos B02 de `0062`. Não é lícito substituir a prova por campos artificiais, mocks ou desativação de triggers.

### 2. Evidência técnica confirmada no código

| Evidência | Consequência |
|---|---|
| `app/models.py`: `NormativeArtifact` possui FK composta para `AcquisitionExecution` de evento `conclusao` e estado `concluida` | Não é possível criar legitimamente o artefacto sem aquisição concluída e ligada ao mesmo identificador/tentativa |
| `app/models.py`: `ExtractionRun` vincula artefacto exato e verificações `authenticity`, `integrity`, `preservation` favoráveis | A extração não começa só porque um PDF tem hash; é necessária a cadeia de verificações |
| `app/models.py`: `ExtractionResult` possui FK composta para `ExtractionRun`, com `run_event=conclusao` e `run_state=concluida` | Resultado de extração exige execução técnica concluída, com identidade, parâmetros e tentativa coincidentes |
| `app/models.py`: `RuleVersion` possui FK composta `(extraction_result_id, extraction_result_record_hash)` | A regra fica ligada à extração exata, não apenas a uma fonte legal textual |
| Migrações `0018`, `0019`, `0020`: **PostgreSQL-only**, append-only, triggers de causalidade e integridade | O `test.db` SQLite não demonstra a equivalência dos gates persistentes PostgreSQL |
| Migração `0025`: exige `sanitized_acquisition_receipts` + `sanitization_verification_records` com verificação favorável antes da aquisição concluída e da extração | Um writer independente tem de satisfazer também a sanitização real quando essa migração estiver instalada; não apenas as sete tabelas fundacionais |
| Migração `0062`: acrescenta `b02_completion_txid`, `a_b02_stamp`, `z_b02_complete_unit` e substitui a função `adr020_require_sanitized_acquisition` | Mesmo que o serviço Python seja novo, uma base que tenha `0062` poderá aplicar gates B02 às tabelas compartilhadas; não assumir independência pela mera troca de serviço |
| `enterprise_b02_noncredential_acquisition.py::stage_completion`: exige base e utilizador B02 exatos | O writer da Fase 4 não pode reutilizar, contornar ou modificar esse executor |
| `pipeline_normativo.py::importar_regras` escreve em `TabelaMVA` | Não é extensão adequada: a Via B foi ratificada para não reduzir a regra a UF/NCM |

**Fontes de código fixadas:**
- Modelos ORM e FKs: app/models.py @ 8e8b72c8
- 0018 — aquisição: migrations/versions/0018_adr020_acquisition_foundation.py @ 8e8b72c8
- 0019 — extração: migrations/versions/0019_adr020_extraction_foundation.py @ 8e8b72c8
- 0020 — regra: migrations/versions/0020_adr020_rule_foundation.py @ 8e8b72c8
- 0025 — sanitização: migrations/versions/0025_adr020_credentials_foundation.py @ 8e8b72c8
- 0062 — mecanismos B02: migrations/versions/0062_adr020_noncredential_acquisition.py @ 8e8b72c8
- Escritor B02: app/services/enterprise_b02_noncredential_acquisition.py @ 8e8b72c8
- Importador legatário de TabelaMVA: app/services/pipeline_normativo.py @ 8e8b72c8

### 3. Tabelas e sessão necessárias

**Predecessores fundacionais efetivos, não apenas três linhas:**

| Ordem lógica | Tabela | Prova/ligação indispensável |
|---:|---|---|
| 1 | `artifact_references` | Identificação e resolução da fonte exata, com eventos e cadeia de predecessor |
| 2 | `acquisition_executions` | Tentativa real, eventos `criacao` → `inicio` → `conclusao`, mesma referência e evidência de bytes obtidos |
| 3 | `normative_artifacts` | Ligação ao evento de aquisição concluída; PDF custodiado por `immutable_bytes` **ou** endereço CAS canónico; SHA-256 real, tamanho e proveniência |
| 4 | `artifact_verification_records` | Verificações favoráveis e cumulativas de autenticidade, integridade e preservação; verificadores e evidências reais |
| 5 | `extraction_runs` | Eventos da extração documentada, mesmo artefacto/hash, extractor/versão/parâmetros/tentativa, verificações anteriores e evento concluído |
| 6 | `extraction_results` | Conteúdo estruturado e evidências, chave composta para a extração concluída e `record_hash` exato |
| 7 | `rule_versions` | Subchave `pa_entrada_22021000_v1`, validade, referências ao decreto, precedência, evidências e FK ao resultado/hash exato |

**Dependências adicionais dependentes da revisão instalada:** a partir de `0025`, os predecessores `sanitized_acquisition_receipts` e `sanitization_verification_records` podem ser mandatórios, com as próprias relações e gates de credenciais. Na `0062`, coexistem provas B02 distintas (`acquisition_mode_bindings`, `noncredential_acquisition_receipts`, `noncredential_sanitization_verifications`) e gates transacionais. **Não foram aqui validadas todas as migrações efetivamente instaladas em nenhuma base.** Antes de projetar um escritor executável, é necessário fixar a revisão Alembic e desenhar a modalidade legítima de aquisição sem falsear provas.

**Sessão recomendada, para futura ratificação:** conexão PostgreSQL expressamente configurada para um **ambiente novo, descartável e fisicamente separado** de `solveris_b02_r4g_test`, com credencial própria de privilégio mínimo. A sessão deve ser transacional, identificar efetivamente base/usuário/schema/revisão, rejeitar qualquer URI implícita e não reutilizar `app.database.SessionLocal` por padrão (que em desenvolvimento pode apontar para `sqlite:///./test.db`). A verificação de preflight deve ser somente leitura; um executor futuro exigirá autorização distinta para qualquer escrita. Nenhuma sessão deve conseguir alcançar o PostgreSQL de produção ou o banco B02, por configuração, privilégio ou roteamento.

**Limite SQLite:** `test.db` pode servir, futuramente e só com autorização própria, como ensaio estrutural de objetos ORM; não como prova de conformidade com triggers, JSONB, imutabilidade e causalidade que as migrações PostgreSQL exigem. **Não proponho escrever em `test.db` neste desenho.**

### 4. Desenho funcional do serviço novo — sem implementação

**Nome arquitetural provisório:** *Custódia ADR-020 PA / candidato condicionado*. Não é nome de ficheiro aprovado nem autorização para criar API ou job.

1. **Pré-admissão, somente leitura:** verificar ambiente físico e revisão do esquema, inexistência de escrita anterior com mesma identidade, autorização de escopo e disponibilidade de bytes imutáveis dos documentos de 2022/2023. Exigir a fonte primária preservada e hash calculado a partir dos bytes; URL, nome ou hash declarado não bastam.
2. **Aquisição independente:** constituir `ArtifactReference` e eventos de `AcquisitionExecution` próprios, com prova real de obtenção/custódia, cronologia, identidade, resultado, hash e tamanho. Cumprir as exigências de sanitização da revisão aplicável; não usar o executor B02, nem assinar falsamente um resultado como `concluida`.
3. **Artefacto e verificação segregada:** vincular cada `NormativeArtifact` à aquisição concluída exata, verificar bytes/sha/tamanho e efetuar provas de autenticidade, integridade e preservação com evidência e segregação adequadas. Uma publicação num portal oficial, por si só, não basta para declarar todos esses gates favoráveis.
4. **Extração técnica real:** registar `ExtractionRun` com executor identificado, parâmetros e transições reais. Produzir `ExtractionResult` apenas se houver extração concluída e conteúdo comprovado. Distinguir a transcrição dos dados do decreto da conclusão sobre sua aplicação jurídica.
5. **Versão de regra:** para a **única combinação ratificada** (`0301001` + `distribuidor_deposito_atacadista`), produzir uma candidata V1 vinculada à fonte de 2022 e uma candidata V2 vinculada à fonte de 2023. Cada `RuleVersion` refere o `ExtractionResult` e o seu `record_hash` exatos, possui `rule_hash` e `record_hash` reais e expõe apenas `pa_entrada_22021000_v1`. V1: 30/08/2022–15/03/2023. V2: a partir de 16/03/2023, **sem afirmar continuidade após 2023 enquanto a cadeia de alterações não for fechada**.
6. **Retorno e leitura independente:** confrontar identidades/hash/datas e permitir ao consumidor já existente apenas `CANDIDATO_CONDICIONAL_COTEJADO_SEM_AUTORIDADE`, ou `ABSTENCAO` quando faltar qualquer prova. Sempre `autoridade_normativa_verificada=False`, `calculo_autorizado=False`, `norma_resolvida=None`. Sem chamada a `buscar_mva`, sem inserção na linha genérica PA.

**Nota transacional:** o cumprimento de sequências cronológicas, verificações e triggers deve ser demonstrado na revisão efetiva do PostgreSQL. Não se deve presumir que tudo cabe num único `COMMIT` ou que chamadas ORM com `flush` substituem os gatilhos de persistência. Numa implementação futura, cada fase material terá autorização e leitura de retorno próprias; falhas interrompem a sequência, sem completar registos fictícios.

### 5. Isolamento obrigatório do B02

- **Separação física e de autoridade:** BD/credencial explicitamente novas e diferentes de `solveris_b02_r4g_test` / `solveris_b02_writer`; sem acesso concedido ao esquema, funções, role ou dados do B02; nenhuma credencial de produção.
- **Separação de código:** zero imports ou chamadas a `stage_completion`, zero alterações a esse método, às migrações B02/G5 ou a `_CAPACIDADES`, G12–G17 e B04.
- **Separação de contratos:** não criar ou alimentar `acquisition_mode_bindings`, recibos B02 ou dados de aprovação G5 por conveniência. Se a revisão instalada tornar tais contratos inevitáveis, isso é **um bloqueio de compatibilidade**, não um motivo para imitá-los.
- **Gates ativos:** nenhuma desativação de trigger, `ALTER TABLE ... DISABLE TRIGGER`, bypass de hooks ou criação de estados concluídos sintéticos; revisões de BD e capacidades validadas antes de qualquer prova de escrita.
- **Sem publicação implícita:** criação de registo documental não é ativação normativa, seleção autorizada, lançamento comercial nem permissão de calcular imposto.

### 6. Alternativas e trade-offs

| Opção | Vantagem | Risco/limite | Parecer |
|---|---|---|---|
| **A. Novo escritor ADR-020 + PostgreSQL segregado** | Respeita FKs/triggers nativos, preserva B02 e permite recibos reais | Exige infra, credencial, worker de aquisição/extração, verificadores e compatibilidade Alembic | **Recomendada, condicional à prova dos gates** |
| B. Estender `pipeline_normativo.py` / `TabelaMVA` | Já tem operações de importação | Viola Via B ratificada; não representa versão documental/CEST/remetente corretamente | Rejeitada |
| C. Reutilizar/adaptar `stage_completion` B02 | Código de aquisição já existente | Credenciais e base fixadas; mistura autoridade e fluxo B02/G5; fronteira proibida | Rejeitada |
| D. Gravar três modelos diretamente via ORM em `test.db` SQLite | Menor esforço aparente | Não demonstra triggers PostgreSQL e pode elidir predecessores obrigatórios | Rejeitada para escritor ADR-020 operacional |
| E. SQL direto em PostgreSQL existente partilhado | Sem novo serviço | Risco de acionar gates/contratos B02 e contaminar infraestrutura; sem segregação | Rejeitada |

### 7. Provas necessárias antes de aprovar implementação

1. **Ambiente PostgreSQL separado:** nome de base, usuário técnico, isolamento e revisão Alembic comprovados, sem acesso B02 ou produção. Não inferir que `test.db` SQLite seja equivalente.
2. **Compatibilidade efetiva:** inspecionar triggers reais de `0018`–`0025`, `0062` e sucessores aplicáveis no ambiente escolhido. **O ponto mais sensível é a função `adr020_require_sanitized_acquisition`:** não aceitar dispensa da prova sanitizada; se os gates exigirem B02, bloquear e submeter nova decisão de arquitetura **sem tocar no esquema B02**.
3. **Fonte e cadeia temporal:** PDFs reais da IOEPA, custódia e SHA-256 dos bytes; provas independentes dos atos, erratas e alterações posteriores a 2023 antes de declarar aplicabilidade atual.
4. **Responsabilidades e hash:** quem obtém, quem verifica independentemente, quem extrai, como se versionam os contratos de canonicalização e como se calculam os `record_hash` reais. Não assumir que hashes B02 ou de fixtures são o contrato geral ADR-020.
5. **Prova de não contaminação:** ensaios futuros, com autorização própria, em base descartável; verificar que nenhuma tabela B02 nem produção foram alteradas; testes negativos de credencial/base, exceção, duplicidade, ausência de prova, rollback e repetição idempotente.
6. **Ratificação específica para execução e escrita:** proposta de código completo antes de qualquer aplicação, script Python com guarda de ocorrências e catraca de duplicação para eventual commit; autorização separada para qualquer gravação, incluindo `test.db`.

### 8. Questões submetidas à ratificação de Miguel

- **D1 — Arquitetura:** ratificar serviço novo, independente de `stage_completion`, com motor de custódia ADR-020 fundacional e sem conexão ao motor de cálculo?
- **D2 — Persistência de ensaio:** ratificar **PostgreSQL segregado**, migrado apenas até `0020_adr020_rule_foundation` (nunca `0025`/`0062`), como alvo futuro de prova de escrita, mantendo `test.db` SQLite fora do caminho operacional ADR-020?
- **D3 — Fronteira B02:** confirmar que qualquer necessidade futura de subir essa base além de `0020` provoca STOP e novo parecer, nunca adaptação das restrições B02 nem fabrico de recibos?
- **D4 — Escopo:** confirmar duas versões históricas documentais **somente** para CEST `0301001` + distribuidor/atacadista, sem autoridade fiscal até as verificações específicas ficarem completas?

**Estado de fecho:** investigação concluída no âmbito documental. **Escritor viável não demonstrado ainda** para o esquema PostgreSQL alvo. Esta proposta não cria autorização, credenciais, schema, serviço, dados, commit ou deploy. O próximo ato é ratificação expressa das decisões D1–D4, seguida de preflight independente; só uma autorização ulterior permite implementação ou escrita.

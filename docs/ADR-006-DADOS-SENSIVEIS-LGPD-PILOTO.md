# ADR-006 — Dados Pessoais, Fiscais e Empresariais de Alto Impacto

**Status:** Activo  
**Data:** 2026-06-25  
**Autores:** Miguel (produto), Claude (código), GPT (auditoria)  
**Ticket:** B11-01B  

---

## 1. Contexto

A Plataforma Tributária L2 processa documentos fiscais que contêm dados pessoais e
empresariais de alto impacto operacional: CPF, CNPJ, chave de acesso NF-e, razão social,
endereço fiscal e valores monetários. O produto está em fase de piloto controlado, sem
abertura pública ainda. Não existia até esta ADR uma decisão explícita e auditável sobre
como esses dados são tratados.

**Nota jurídica:** Nos termos do art. 5º, II da LGPD (Lei 13.709/2018), dado pessoal é
"informação relacionada a pessoa natural identificada ou identificável". CPF enquadra-se
nesta definição. CNPJ, chave NF-e e demais identificadores fiscais/empresariais são
tratados nesta ADR como dados de **alto impacto operacional** — terminologia operacional
interna que **não** confunde com "dados sensíveis" nos termos do art. 11 da LGPD, salvo
quando correlacionados com categorias especiais expressamente listadas nesse artigo.

A auditoria B11-01 (2026-06-25) produziu o mapa de exposição que fundamenta esta decisão.

---

## 2. Decisão

**CPF, CNPJ e chave NF-e são dados operacionais necessários no piloto.**

No estado actual, ficam em texto persistido por necessidade funcional — sem criptografia
nem tokenização. Esta é uma decisão temporária e consciente, não um defeito arquitectural.

**É proibido expor esses dados em:**
- logs de aplicação ou sistema
- fixtures de teste no repositório
- mensagens de erro públicas (HTTP responses)
- documentos de desenvolvimento ou handoffs

**Criptografia/tokenização fica como revisão obrigatória antes de:**
- escala para utilizadores além do piloto controlado
- integração externa ampla (contabilidade, SEFAZ, terceiros)
- entrada de dados reais em volume

---

## 3. Dados Classificados

| Dado | Localização | Classificação | Estado actual |
|------|------------|--------------|--------------|
| `User.cpf` | `usuarios.cpf` | Pessoal — alto impacto operacional | Texto puro, necessário para registo único |
| `Empresa.cnpj` | `empresas.cnpj` | Empresarial — alto impacto operacional | Texto puro, necessário para resolução por emitente |
| `DocumentoFiscal.chave_nfe` | `documentos_fiscais.chave_nfe` | Fiscal — alto impacto operacional | Texto puro, necessário para deduplicação |
| `DocumentoFiscal.conteudo_sha256` | `documentos_fiscais.conteudo_sha256` | Fingerprint | Hash irreversível — aceitável |
| XML bruto | Memória (`xml_bytes`) | Fiscal — alto impacto operacional | Não persistido como bytes; só hash e campos extraídos |
| `RequestLog` | `request_logs` | Operacional | `method`, `path`, `status_code`, `user_id`, `ip`, `user_agent` — sem body/query/headers |
| PDFs gerados | Memória (`BytesIO`) | Fiscal — alto impacto operacional | Não escritos em disco; gerados e devolvidos em memória |

---

## 4. Regras em Vigor (Piloto)

### 4.1 Logs

- **Proibido** logar `body` de requests
- **Proibido** logar `headers` (incluindo `Authorization`)
- **Proibido** logar `query_params` com dados identificativos
- **Proibido** logar CPF, CNPJ, chave NF-e ou XML bruto em qualquer nível
- `RequestLog` persiste apenas: `method`, `path`, `status_code`, `user_id`, `ip`, `user_agent`
- Retenção por defeito: 30 dias (configurável via `REQUEST_LOG_RETENTION_DAYS`)

### 4.2 Repositório e Fixtures

- **Proibido** commitar XML real de qualquer cliente ou empresa real
- **Proibido** commitar CPF ou CNPJ reais em fixtures, seeds ou testes
- Todas as fixtures devem usar dados sintéticos/anonimizados
- Ficheiros de fixture com dados fiscais devem ter nome explicitamente sintético
  (ex: `xml_icms10_st_sintetico.xml`, não `xml_icms10_st_real.xml`)
- CNPJ de fixture: usar sequências claramente fictícias (ex: `12345678000199`)
- Chave NF-e de fixture: usar chave construída com CNPJ fictício

### 4.3 Mensagens de Erro

- **Proibido** expor CPF, CNPJ ou chave NF-e em respostas HTTP de erro (`detail`)
- `DuplicataFiscalError` usa chave interna — nunca exposta directamente ao cliente HTTP
- Erros de validação devem indicar o tipo de problema, não o valor do dado

### 4.4 Ambiente de Desenvolvimento

- Dados de produção não devem ser copiados para ambiente local sem anonimização
- Dumps de BD para desenvolvimento devem mascarar CPF, CNPJ e chave NF-e

---

## 5. O Que Esta ADR Não Decide

Esta ADR **não decide**:

- Implementação de criptografia em repouso (AES-256, etc.)
- Tokenização de CPF/CNPJ
- Política completa de retenção documental (prazo para XMLs, relatórios, homologações)
- Fluxo de exportação de dados do utilizador (LGPD Art. 18)
- Fluxo de eliminação de dados do utilizador (LGPD Art. 18)
- Pseudonimização para análise estatística
- Política de backup e recuperação com dados de alto impacto operacional

Estes pontos ficam para **Bloco 11 fase 2**, após abertura do piloto e antes de escala.

---

## 6. Consequências

**Positivas:**
- Decisão explícita e auditável — elimina ambiguidade de "está protegido por defeito"
- Regras claras para desenvolvimento, testes e fixtures
- Base documental para futuras auditorias de conformidade LGPD

**Negativas / Riscos controlados:**
- CPF/CNPJ em texto puro expõe a BD a leitura directa se acesso não autorizado ao PostgreSQL
- Chave NF-e em texto facilita correlação de documentos se BD for comprometida
- Sem criptografia, dump de BD = dados em claro

**Mitigação no piloto:**
- Acesso à BD controlado via Railway (sem acesso público, só Railway env)
- Sem abertura pública; acesso restrito a piloto controlado
- Dados em volume mínimo (piloto controlado)

---

## 7. Revisão Obrigatória

Esta ADR deve ser revisitada e possivelmente substituída por ADR-007 antes de:

- [ ] Abertura a utilizadores externos ao piloto
- [ ] Integração com APIs externas (Mercado Pago, SEFAZ, contabilidade)
- [ ] Volume > 100 utilizadores reais
- [ ] Entrada regular de XMLs reais fora de piloto controlado
- [ ] Qualquer auditoria externa de conformidade

**Responsável pela revisão:** Miguel (produto) + GPT (auditoria arquitectural)

---

## 8. Referências

- `ROADMAP_ABERTURA_UTILIZADORES.md` — Bloco 11
- `ADR-004-VINCULO-SOBERANO-CONTADOR-DT-CONTADOR-01.md` — controlo de acesso operacional
- `ADR-005-CARTEIRA-CONTADOR-ANTI-CAPTURA.md` — anti-captura de carteira
- Auditoria B11-01 — mapa de exposição de dados (2026-06-25)
- LGPD (Lei 13.709/2018) — Art. 5º, II (definição de dado pessoal); Art. 7 (bases legais); Art. 11 (dados sensíveis — aplicável condicionalmente; CPF/CNPJ/chave NF-e não se enquadram por defeito); Arts. 18 e 46 (direitos do titular e segurança)

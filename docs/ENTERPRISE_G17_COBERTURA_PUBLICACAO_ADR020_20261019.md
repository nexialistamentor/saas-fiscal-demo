# SOLVERIS Enterprise G1.7 — janela de publicação e cobertura ADR-020 (read-only)

**Base obrigatória:** `work/fiscal-assumptions-c0` HEAD `16af35989194c095eaa8fda5e4501d7096fc2334` (G1.6). Nenhuma fonte oficial é considerada autenticada nesta fase.

## Intervenção

`app/services/enterprise_g17_publication_coverage_checkpoint.py` reutiliza a cadeia **G1.6 → G1.5 → G1.4 → G1.3 → I2/G1.2/G1**, com os mesmos bytes do documento e o mesmo objeto de leitura de BD. Apenas após o G1.6 satisfazer posse/provenience e regra interna, coteja identificadores explícitos de `CoverageContract`, `CoverageCheckpointRecord` e `CoverageLedgerEntry` do ADR-020.

O adaptador vincula a origem do `RuleVersion → ExtractionResult → NormativeArtifact → ArtifactReference.source_id` à do contrato de cobertura (`CoverageContract.source_id`). Não aceita que um contrato arbitrário de outra fonte confira cobertura a uma regra diferente. Exige contrato `ratificada`, janela temporal explícita, checkpoint inteiramente avaliado sem lacunas e entradas ordenadas e contíguas `1..covered_through`, todas com observação e processamento positivo. Limite deliberado de **128 unidades** por item. Uma relação temporal de risco detectada no G1.6 bloqueia o cotejo de cobertura desse item.

### Resultado máximo

`JANELA_ADR020_COTEJADA_NAO_EXAUSTIVA`: as unidades **explicitamente enumeradas** no snapshot conferem com o ledger do ADR-020 e a origem normativa interna. O resultado continua a marcar como `False`:

- `edicao_oficial_assinatura_validada`, `fonte_primaria_autenticada`;
- `cobertura_publicacoes_exaustiva`, `ausencia_revogacao_comprovada`;
- `vigencia_juridica_comprovada`, `autoridade_fiscal`, `credito_confirmado`, `checkout_autorizado`, `usavel_comercialmente`.

**Pontos de atenção:** um checkpoint fornecido pelo chamador não prova que é o último; um calendário sintético não prova que todas as edições oficiais do período foram observadas; o estado interno `covered` não autentica uma assinatura ICP-Brasil. Datas da NF-e são observadas em bytes privados, sem carimbo externo. O tratamento de fuso é deliberadamente conservador para o intervalo completo do dia e não promove validade jurídica.

## Fonte externa para futuro piloto verificável (não executada pelo adaptador)

Para o Pará, a Imprensa Oficial publica edições do Diário Oficial eletrónico em PDF, com orientação para inspecionar a certificação digital no **Painel de Assinaturas**:

- https://www.ioepa.com.br/2012/conteudo.aspx?cont=6
- https://www.ioepa.com.br/portal/conteudo.aspx?cont=82

O piloto real deverá adquirir PDFs oficiais exatos, validar criptograficamente assinaturas e a cadeia confiável do signatário (incluindo estado temporal da assinatura e revogação do certificado), provar edição/data/ato e estabelecer a **cobertura exaustiva** dos períodos e publicações pertinentes. Depois precisará cotejar conteúdo, relações de alteração/revogação e aplicabilidade legal por NCM/CEST/CFOP/CST/UF. Um mero URL HTTPS, certificado TLS, hash de download, PDF ou linha `ratificada` não bastam.

## Testes e proteção operacional

- 36 testes sintéticos isolados (sem rede, empresa, BD real ou escrita), incluindo adulteração de identidade, cross-source, fronteira de cobertura, datas, unidades e revogação.
- Smoke integrado com módulos reais I2/G1.2/G1.3/G1.4/G1.5/G1.6 e **objetos de modelo reais**, mas toda NF-e, regra, empresa e ledger **sintéticos**, DB fake read-only.
- Regressões existentes selecionadas; a suíte integral não é afirmada.
- Instala **apenas** três ficheiros novos (serviço, teste, documento); não modifica outros componentes. Commit e push somente após revisão separada.
- Não alterar MEI, `app/database.py`, modelos, migrations, motores, dados reais, SEFAZ, pagamentos, deploy ou fonte normativa oficial.

**Próxima etapa:** ligação independente aos bytes de publicação oficial e verificador de assinatura/cadeia de confiança, seguida de prova de cobertura real e aplicação legal. A G1.7 não converte nenhum dos campos negativos em `True`.

## Revisão de limites temporais — G1.7-R1 (19/10/2026)

A primeira versão comparava somente `datetime.date()` dos extremos do contrato e do checkpoint. Isso podia aceitar uma janela iniciada ao meio-dia da operação como se incluísse o dia inteiro. Foi reproduzido com dados sintéticos (RED), portanto o commit da versão inicial foi bloqueado.

A revisão exige **intervalos UTC com comparação integral de hora e fuso**:
- limite inferior: `00:00 UTC` da data civil observada na NF-e;
- limite superior: `06:00 UTC` do dia seguinte, incluído;
- tanto o contrato quanto a janela enumerada devem abranger integralmente esse intervalo.

Como a G1.6 expõe apenas a **data**, sem a zona horária vinculada e verificada, os limites foram escolhidos conservadoramente para cobrir a totalidade do dia nas zonas brasileiras de UTC+00 até UTC−06, sem inferir um fuso por UF. O intervalo contém horas excedentes; uma janela mais estreita pode ser legítima, mas permanece bloqueada até existir o vínculo temporal exato. Esta disciplina não é prova de tempo oficial, assinatura, publicação externa ou ausência de revogação.

Testes adicionados: início parcial, término parcial, contrato com extremos parciais, normalização de fuso e caso positivo de limites completos. O contrato G1.7 permanece **read-only e não comercial**, e nenhum módulo G1.6 ou anterior foi modificado.

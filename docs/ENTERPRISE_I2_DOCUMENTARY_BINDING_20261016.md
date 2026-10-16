# SOLVERIS Enterprise — I2: ligação documental causal (16/10/2026)

**Branch/HEAD obrigatório:** `work/fiscal-assumptions-c0` / `c912987fc31711ae4472cd4cf0174eb7049ae82b`.

## Objetivo

Criar ponte exclusivamente interna entre a **I1 (PIS/Cofins, ICMS próprio ≠ ST)** e a evidência já persistida sob `RelatorioAnalise` + `DocumentoFiscal` + `ItemFiscal` + `empresa`, reutilizando `verificar_resultado_persistido` e `validar_vinculo_documento_relatorio`. Nenhum motor existente é reescrito.

## Contrato de entrada e fronteiras

- Invocação exclusivamente server-side, com `db`, `authenticated_user_id`, `empresa_id`, `relatorio_id` e **bytes exatos** da NF-e; sem rota HTTP, sem chamada externa, sem DB produtiva nos testes.
- Empresa vinculada ao utilizador e ao CNPJ emitente; regime declarado estritamente `real` ou `presumido`, nunca MEI.
- Relatório `xml_analise` concluído, resultado selado com fingerprint e proveniência; vínculo armazenado de usuário/empresa/relatório/documento/chave/hash (P1-03B).
- SHA-256 calculado sobre os bytes recebidos = SHA persistido; chave NF-e, protocolo (se existir), CNPJ emitente e data de emissão coerentes; NF-e de **saída normal**.
- Valores `vProd`, `vBC`, `vICMS` extraídos do XML por item com `nItem`, CFOP/NCM e modalidade permitida; ST (`vST`/`vICMSST`) apenas **campo separado**, nunca excluído automaticamente como ICMS próprio.
- Itens XML reconciliados com itens ORM persistidos por NCM, CFOP, valor do produto e `valor_icms`. Comparação por multiconjunto mantém contagem de linhas; `nItem` é identidade do item XML, **não equivale a `ItemFiscal.id`** no esquema atual.
- Apenas subconjunto de NF-e com `vNF == soma(vProd)` é aceito nesta etapa experimental, sem transformar isso em regra geral de receita tributável.
- I1 é chamada com contexto estritamente derivado da NF-e/BD; não aceita valores monetários livres do chamador. O seu motor existente é usado apenas para **simulação condicional não publicável**.

## O que ainda NÃO está provado

O vínculo de bytes **não autentica** a autorização da SEFAZ, assinatura/certificado, destinatário económico, enquadramento normativo do facto, CST e incidência efetiva de PIS/Cofins, regime de escrituração, tributação sobre receita reconhecida, exclusões por decisão jurídica, EFD-Contribuições, apuração de todos os documentos do mês, pagamentos, indébito ou crédito fiscal. `finNFe=1` não elimina sozinho essas limitações.

**Resultado obrigatório:** `uso=INTERNO_NAO_PUBLICAVEL`, `checkout_autorizado=False`, `diagnostico_empresarial_completo=False`, `comprovacao_normativa=False`. Os valores PIS/Cofins são **apenas cenários por NF-e**, não valores devidos na competência. PIS e Cofins e os créditos continuam separados; créditos não são apurados.

## Verificação

RED causal (módulo inexistente) -> GREEN dos testes I2 com NF-e sintética e modelos em memória -> I1 (16) -> I0 (7) -> regressões PDF/checkout. Verificar SHA dos ficheiros, branch, HEAD, remote e a ausência de modificações alheias. Nenhum commit/push/deploy automático nesta etapa.

## Continuidade I3

I3 deverá tratar **cobertura por competência e regime**, reconciliação de múltiplos documentos e fontes EFD/NFS-e quando existirem, e fronteira normativa temporal, sem inventar dados ausentes. Os 52 componentes Enterprise permanecem no contrato até ao diagnóstico integral e à venda autorizável.

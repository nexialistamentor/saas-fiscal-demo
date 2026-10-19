# SOLVERIS Enterprise G1.4 — enquadramento normativo *candidato* por operação

**Base ratificada:** `work/fiscal-assumptions-c0`, HEAD `a9b940299da7ef1f13269c1f40bbf9c433e7c19f` (G1.3).

## Objectivo e fronteira

Criar um adaptador **interno, read-only** que execute a cadeia existente **G1.3 → I2 → G1.2 → G1.1** antes de examinar qualquer candidato normativo. Verifica posse, relatório, fingerprint, bytes XML e identidade dos itens segundo os gates já existentes; depois compara por **item/UF/NCM/CEST/CFOP/CST/regime/operacao/modalidade/competência/data de vigência/ato/versão** contra metadados **candidatos, expressamente não autenticados**.

G1.4 **não altera** `fiscal_utils`, `tabela_normativa_service`, `st_service`, `MotorFiscal`, o schema da base, o pipeline normativo ADR-020, I2 ou G1.3. A ligação ao resolvedor real já existe em G1.2. O G1.4 não replica o cálculo e exige que o `fonte_legal` do candidato coincida com a fonte declarada pelo G1.2 para o **mesmo item**.

### Entrada `candidatos_normativos`

Lista explícita de até 500 dicionários com cardinalidade máxima de um por índice de item. Campos exactos: `indice_item`, `uf`, `ncm`, `cest`, `cfop`, `cst`, `regime`, `operacao` (`saida_interna`), `metodo_base` (`iva_st`), `vigencia_inicio`, `vigencia_fim`, `fonte_legal`, `url_fonte` (HTTPS sintaticamente válida), `sha256_texto_normativo_declarado`, `versao_ato`. Esses campos são **alegações externas** e não credenciais nem provas. O SHA é um digest **declarado, não verificado contra texto primário**. Não se aceita `fonte_primaria_autenticada`, `credito_confirmado`, `checkout_autorizado` nem quaisquer chaves extras.

O resultado máximo é `COERENCIA_ESTRUTURAL_CANDIDATA_SEM_TRUST`. O nome da regra e a presença de CEST não provam que a mercadoria ou operação esteja sujeita a ICMS-ST. A ausência de CEST também **não comprova não incidência**. Vigência utiliza a `dhEmi` declarada no próprio XML e exige autenticação temporal externa em gate posterior.

### Regras de fail-closed

1. **G1.3 deve passar primeiro**, usando os mesmos `db`, identidade e bytes. Qualquer violação de posse, hash, autoridade indevida ou formato é STOP.
2. A empresa é lida novamente, sem escrita, e deve ter identidade/posse coerentes e regime `real` ou `presumido`; MEI fica excluído nesta fronteira.
3. O XML deve ser NF-e modelo 55, saída normal intrastadual. As classificações NCM/CFOP e `nItem` não podem divergir do G1.2, e a competência tem de coincidir com a da G1.3.
4. Candidato único por item, valores exactos, intervalo temporal estrito, fonte legal idêntica ao resolvedor G1.2, e simulação G1.2 efetivamente existente. Campos ambíguos, data fora da janela, fonte divergente ou redução/base não tratada bloqueiam a classificação.
5. Toda saída fixa `autoridade_fiscal=False`, `fonte_primaria_autenticada=False`, `credito_confirmado=False`, `checkout_autorizado=False`; não escreve nem coloca produto à venda.

### Limites e pendências

- **CEST/NCM/CFOP/CST** são identificadores estruturais, não fundamento completo do regime tributário por produto, benefício, segmento, exceção, destinatário ou sujeição a ST.
- Falta **obter/custodiar ato normativo primário** íntegro, validação de URL/assinatura ou publicação oficial, versão e vigência realmente aplicáveis, conflito com exceções e ST por tipo de operação.
- ICMS próprio G1.2 é deduzido de valor informado no XML, não recalculado de norma independente. Sem EFD/recolhimento e autorização SEFAZ.
- **PMPF permanece bloqueado** em G1.2; G1.4 não desbloqueia essa modalidade.
- Os 28 testes unitários são sintéticos, e o smoke importa I2/G1.2/G1.3 reais com **XML, empresa e regra inteiramente sintéticos**. Não é teste com normativa real nem end-to-end produtivo.
- LCR histórica I13 permanece pendente e não é utilizada aqui.

### Disciplina de intervenção

Instala somente três ficheiros novos no worktree Enterprise após RED de ausência, hashes, testes, smoke real-sintético e regressões. Sem commit, push, MEI, base empresarial, SEFAZ, rede ou deploy. Após sucesso, ratificar diffs e hashes antes do commit separado.

**G1.5 futuro:** autoridade de fonte primária e hierarquia temporal verificáveis sem confiar em metadados autoclassificados, com prova de exceções, tipo de operação, enquadramento e conflito normativo. Integrar com ADR-020 após ratificação, mantendo EFD/recolhimento e autenticidade documental como gates separados.

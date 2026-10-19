# SOLVERIS Enterprise G1.3 — vínculo de sujeito, documento e item ST

**Base ratificada:** branch `work/fiscal-assumptions-c0`, HEAD `b44eb363ab6997251cd553596d1edf5b85207546` (G1.2).

## Intervenção

Novo adaptador interno `app/services/enterprise_g13_subject_st_bridge.py` liga **I2** (posse, relatório persistido/fingerprint, vínculo XML/documento, hash e itens persistidos) ao **G1.2** (simulação ST/MVA itemizada com os motores existentes), reutilizando exatamente os mesmos bytes e o mesmo objeto DB, numa chamada somente de leitura.

1. A I2 é chamada primeiro. Em falha, o G1.2 **não** é chamado.
2. A saída da I2 deve ser `ENTERPRISE_I2_DOCUMENTARY_BRIDGE_V1`, com `DOCUMENTO_INTERNO_RECONCILIADO`, e todos os flags de trust/crédito e comércio negativos.
3. Os bytes SHA-256, a competência declarada, o número de itens e as suas identidades NCM/CFOP/índice devem coincidir rigorosamente entre I2 e G1.2. A divergência é STOP.
4. A chamada real de G1.2 continua condicional: apenas caso estreito ICMS10, operação intrastadual modelo 55, normal, MVA e sem componentes acessórios; PMPF, CEST, redução, exceções e outros casos permanecem não comprovados.
5. O resultado G1.3 inclui identificação documental interna, resumo da simulação G1.2 e **nega** em todos os casos autoridade fiscal, crédito, checkout, autenticação SEFAZ, norma primária provada, ICMS próprio recalculado e escrituração EFD.

## Limites preservados

- O indicador `posse_e_proveniencia_interna_i2=True` comprova somente a verificação **interna** efetuada pela I2; não é uma assinatura ICP-Brasil, validação SEFAZ ou norma aplicada.
- A fonte normativa devolvida pelo resolvedor pode conter metadados declarados no DB. O seu conteúdo **não autentica o ato normativo original**, nem a sua aplicabilidade por CEST/operação.
- A dedução de ICMS próprio no cálculo G1.2 provém do XML, não de recálculo independente.
- Um XML único não prova toda a competência, EFD, recolhimento, direito à restituição ou histórico de créditos.
- O G1.3 não injeta resultados em relatório, UI, API ou checkout; ligação ao produto completo deverá ter gate próprio.
- Nenhum XML empresarial real, senha, token, certificado privado, SEFAZ, rede, banco de produção, MEI, deploy ou pagamento.

## Provas

- 24 testes sintéticos isolados G1.3 com negativas de fraude de posse, hash, competência, item, contagem, norma e autoridade.
- Smoke com os **módulos reais** I2, G1.2, G1, parser e provenance, mas XML/empresa/relatório totalmente sintéticos e DB fake somente de leitura.
- Regressões selecionadas: G1.1 + I2 + origem ST e análise XML existentes. Não substitui suíte integral.
- Após verificação Windows, consultar SHA-256 dos três novos ficheiros, diff staged/unstaged e regressões, depois decisão separada de commit/push.

## Próximo gate

G1.4: demonstrar associação precisa UF/NCM/CEST/CFOP/CST/atividade/regime, versão temporal da norma oficial e exceções por operação, com fonte primária autenticada, mantendo prova de ICMS próprio e de EFD/recolhimento em trilhas separadas. Não elevar resultados G1.3 a conformidade fiscal jurídica até todos os requisitos estarem demonstrados.

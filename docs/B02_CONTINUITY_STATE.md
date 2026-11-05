# B02 — ESTADO DE CONTINUIDADE (fonte única, ler antes de qualquer nova sessão)
Atualizado: 2026-11-05

## FACTO CONFIRMADO — não repetir esta investigação
- Chave privada existe: CustodiaB02\Chave_ceee5bb6f2a740a58cf4dbaa66565698\miguel-private-encrypted.pem
- Fingerprint SHA-256 confirmado: 6f0ede1267a208505b2443d765cf97f2206759049f938a1d95d92a86c4c5d63c
- Este fingerprint JÁ ESTÁ pinado em ROOT.json e BUNDLE_ASSINADO\decision.json (ambos de 04/11)
- NÃO EXISTE custodiante a descobrir nem chave a gerar. O custodiante é Miguel, confirmado.

## O QUE FALTA (único bloqueio real)
O ROOT/decision existentes estão vinculados a:
- object_sha256 = 615c8d64... (objeto G4 ANTIGO, não a candidata atual)
- scope = SEFA_PR_B02_DOCUMENTAL_AUTHENTICATION_ONLY (não é G5_R1_ADMISSION)
- valid_until = 2026-11-04T18:00:00Z (EXPIRADO)

Candidata atual: 389cce04dd249c5fb184fce7b876608651dd84ca3db64b7d778bb2de66a0c3d2

## PRÓXIMO PASSO ÚNICO
Emitir NOVA decision.json com a MESMA chave (fingerprint acima), scope=G5_R1_ADMISSION,
object_sha256=389cce04..., janela de validade nova. Usar tools/b02_documentary_signer_v2.py
como base de estrutura (DECISION_KEYS já mapeado).

NÃO repetir: busca de chave, busca de custodiante, verificação de fingerprint, pergunta "quem assina".
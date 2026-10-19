# SOLVERIS Enterprise G1.9-R2 — recuperação de metadados CAS no Windows (19/10/2026)

## Evidência de falha

No checkout Windows: 8 falhas G1.9, 200 testes PASS, 2 SKIP. Todas as falhas registadas convergiram no `G19_CAS_OBJETO_TROCADO_DEPOIS_DA_LEITURA` imediatamente após `guardar_pdf_cas_g19`, na comparação dos atributos entre `os.fstat(fd)` e `Path.stat()` após o fecho do descritor. A discrepância de atributo exato não foi isolada: não afirmar causa específica sem rastreio adicional.

## Intervenção R2

Substituir exclusivamente `_read` no serviço G1.9. Em vez de comparar os metadados capturados pelo descritor com os obtidos posteriormente pelo caminho, manter **dois descritores abertos em simultâneo** para o mesmo caminho CAS. Em cada um, verificar tipo de ficheiro, tamanho, ausência de hardlinks, estabilidade de atributos no próprio descritor e SHA-256 real dos bytes. Comparar identidade `(st_dev, st_ino)` entre os dois descritores e igualdade integral dos bytes, mantendo a rejeição de reparse/symlink e a criação exclusiva.

A prova de custódia externa ou imutabilidade **não** fica estabelecida por este procedimento. Sem confiança ICP-Brasil temporal, sem direitos fiscais, sem checkout e sem alterações à G1.5/G1.8.

## Cobertura adicional

Testes 36 e 37: divergência de metadados somente de `Path.stat()` não produz falso alarme; uma tentativa de substituir o segundo descritor por outro ficheiro com bytes divergentes é bloqueada. Regredir os testes G1.9 mais G1.8–G1.4 e verificar PDF IOEPA real fora do repositório.

## Âmbito

Duas substituições controladas de ficheiros **não rastreados** G1.9 (serviço e teste) mediante confronto de hashes R1, mais este documento novo. Sem apagar artefactos, sem reabrir branches, sem BD, sem deploy nem commit/push até GREEN comprovado no Windows.

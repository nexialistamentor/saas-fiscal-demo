# Dados CNAE — Plataforma Soberana L2

**Fonte:** IBGE/Concla — CNAE 2.0

**Versão:** 2.0

**Vigência:** 2007 (com actualizações)

**Encoding:** UTF-8 (convertido de Windows-1252 original)

**Actualização:** versionar novo ficheiro com data no nome

## Ficheiros

- `cnae_2_0_subclasses.csv` — lista completa de 1.301 subclasses

- `cnae_permite_mei.json` — CNAEs permitidos para MEI (fonte: Portal do Empreendedor)

## Estrutura CSV

codigo_subclasse, descricao, codigo_classe, codigo_grupo,

codigo_divisao, secao, permite_mei, vigencia_inicio

## Princípio soberano

Dados versionados no repo — sem dependência de API externa em runtime.

Motor fiscal lê ficheiro local — decisão auditável e reproduzível.

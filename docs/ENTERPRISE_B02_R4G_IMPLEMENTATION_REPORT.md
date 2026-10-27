# 02-R4G — candidato local de implementação, R1

Estado: preparado para revisão e instalação local autorizada. Não aplicado ao
PostgreSQL. Bloco 02 aberto; Bloco 03 bloqueado. Nenhum fecho institucional é
inferido deste relatório.

Base recebida: work/fiscal-assumptions-c0,
b45ef5396189f5b6be1156535c9af9b19cca17b4. O instalador exige essa base, staging
vazio, a alteração G113 preservada e os hashes protegidos. A validação feita
nesta sessão usa uma cópia local dos modelos e uma Base declarativa em memória;
o stub de database não integra o pacote instalável.

Entradas congeladas: ADR original b57c4c20cb8976940e35b91469cd998dd9a6367e96c4e12c096a3f02a31135ad;
adenda ratificada 0359ab0bd03fee6127330158bc1b5388188aba650ee6e74fb2c762d1b85857fa;
contrato RED d311c8cba80403433b7f86808f1f16c674b8aae2e36b756e4b9e21bf8053449b;
bateria física ee04b0b763130a73bd98f9e50c86251073626da4ccdc1bf1a02c9ed2b7b2b6e0.
Não se alteram esses documentos ou testes. Os gates G0/G1 recebidos não foram
reexecutados. O novo ensaio do contrato mede a implementação candidata.

## Delta concreto

| Caminho autorizado | Alteração candidata |
| --- | --- |
| app/models.py | Apêndice de três entidades de prova, FKs compostas, checks e metadados prospectivos de transação em aquisição/artefacto; prefixo original preservado |
| app/services/enterprise_b02_noncredential_acquisition.py | Fronteiras fechadas de modo, serialização inteira UTF-8, montagem da unidade CAS em transação externa, releitura idempotente exata; sem commit interno ou rede |
| migrations/versions/0062_adr020_noncredential_acquisition.py | Três tabelas append-only, hashes/txid atribuídos no servidor, constraints diferidas, guards contra contradição credenciada e substituição prospectiva da função defeituosa |
| tools/enterprise_b02_r4g_cas_persistence.py | Gerador inerte de fixtures sintéticas a partir de exportação exata de políticas; entrada real bloqueada |
| docs/ENTERPRISE_B02_R4G_IMPLEMENTATION_REPORT.md | Este estado e limites |

Predecessor da candidata: 0061_enterprise_documental_checkout_intent. A migration
não cria extensão, base, papel, grant, política ou ativação; não reescreve dados
nem altera migrations históricas. Downgrade destrutivo é recusado. Os dois
campos prospectivos b02_completion_txid são anuláveis para o histórico existente;
apenas novos INSERT recebem o xid integral do servidor. Não se usa xmin nem
variável de sessão como prova de atomicidade. A nova unique composta na tabela
original permite a FK física id/hash/execução/referência/tentativa.

A correção de extração usa ramo explícito por tabela: run artefacto/hash →
artefacto → terminal/tentativa → provas. Não lê NEW.acquisition_execution_id
num extraction_run. Os triggers originais permanecem instalados, sem janela de
desativação. Os gates jurídicos 0019 permanecem intactos. Ausência de modo novo
leva ao circuito original restritivo, nunca à aceitação CAS/pública.

## Provas desta sessão e limites

- Contrato congelado: 28 PASS locais, incluindo o controlo credenciado, com
  inspeção de metadados e serviço; sem ligação ao PostgreSQL.
- Sintaxe Python, FKs de metadados, vetores de canonicalização, exclusões A6,
  rejeição de tipos não canónicos e ausência de transação externa: validados.
- Alembic: geração offline do DDL concreto, três CREATE TABLE; nenhuma aplicação.
- Fixtures: estrutura, estágios, referências e renderização SQL validados em
  memória com contexto de desenho claramente assinalado como não existente.
- Não se afirma validação sintática pelo servidor PostgreSQL, comportamento de
  triggers, 28 PASS físicos, concorrência provada ou atomicidade física provada.
  Esses resultados dependem de G3, do writer e dos predecessores sintéticos reais.

A versão inteira de serialização é fixada em CANONICAL_CONTRACT.json antes da
materialização do novo schema; não modifica o teste RED. Valores fracionários,
bytes e chaves não textuais não são admitidos no contrato novo. Bytes pertencem
ao artefacto; timestamps armazenados são canonicalizados no servidor em UTC.
O hash integral exclui o próprio record_hash; o hash material do recibo conserva
as exclusões exatas A6. Os vetores incluem Unicode, escapes, arrays e inteiros.
A equivalência desses vetores com PostgreSQL ainda exige ensaio G3.

## Limite deliberado deste candidato local

O candidato admite somente provas novas com provenance.synthetic_only=true.
Não está pronto para persistência documental real: não valida criptograficamente
um comprovativo de independência de engine. Dois nomes e um hash não demonstram
segregação efetiva. O exemplo de fixture declara que essa prova é simulada.
O serviço não produz uma verificação favorável a partir do PDF; recebe prova
subordinada de um verificador, e a migration mantém a barreira a dados reais.
A remoção dessa barreira exigiria implementação delimitada e provas próprias;
não é um parâmetro de execução nem pode ser autorizada por um campo no JSON.

O grant de regras B02_POLICY_GRANT_V1 é contrato técnico proposto, subordinado a
PolicyVersion/PolicyActivation exatas e ativas. Não cria policy_type security ou
sanitization. O pedido sintético propõe regras desses propósitos numa policy
canónica automation_envelope, ainda sem criação/ativação. Isso não ratifica uma
política institucional real nem demonstra toda a sua eficácia/lifecycle.
Intervalos from/until, modalidade, domínio, escopo, ator, adaptador, contrato,
engine e verificador precisam de correspondência explícita. Falta bloqueia.
As fixtures de desenho não são exportações do catálogo e não servem ao runner
físico. O gerador CLI exige context_origin=ISOLATED_DB_EXACT_EXPORT e SHA-256.

Os outcomes não favoráveis estão modelados, mas este circuito de conclusão exige
unidade favorável completa; persistência separada de diagnósticos de falha não
está implementada neste candidato. Não existe aquisição pública de rede.

## Próximo gate delimitado

Rever o diff concreto e 0062_REVIEW_OFFLINE.sql. A instalação local e o contrato
em memória não autorizam aplicar DDL. Antes de G3 aprovar especificamente:

1. Aplicação canónica de 0062 apenas em solveris_b02_r4g_test, admin separado;
   sem acesso a solveris_test, MEI, outras bases ou produção.
2. Grants mínimos SELECT, INSERT nas três tabelas novas ao writer existente,
   sem UPDATE/DELETE/TRUNCATE/TRIGGER, schema create ou privilégios administrativos.
   O pacote não executa esses grants.
3. Preparação das políticas/ativações estritamente sintéticas pela cadeia
   canónica existente. O pedido fornece conteúdos de desenho; não fornece um
   bypass de bootstrap, decisões ou triggers. Fixar IDs/hashes reais dessa preparação.
4. Exportação exata do contexto preparado e geração de namespace novo. Rever
   fixtures e hashes antes de ensaios; a fixture de concorrência é de uso único.
5. Ensaios físicos completos em ordem, -x, sem distribuição/reordenação. O caso
   11 requer commit sintético explícito e o caso 24 depende da sua releitura.

Depois de G3, se autorizado e favorável, continuar G4 com políticas/provas reais.
Este candidato mantém STOP_REAL_POLICY_OR_EVIDENCE_MISSING para esse percurso.
Não solicitar escrita documental real, commit Git, push, merge ou deploy com
base nos resultados presentes. Não se cria autoridade paralela: não há novas
entidades de decisão/ativação, nenhum grant institucional, nenhuma promoção
normativa e nenhum caminho para cálculo, crédito ou checkout.

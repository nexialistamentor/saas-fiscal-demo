# MG — Mapeamento anexo → NCM (PMPF / SAIF 062/2025)

Este documento acompanha o parser `app/services/parsers/sefaz_mg_pdf_parser.py`
(Opção A: **NCM fixo por anexo**, sem coluna NCM nas tabelas PDF).

## Fonte normativa

| Campo | Valor |
| ----- | ----- |
| Ato | Portaria SAIF nº 62, de **22 de dezembro de 2025** |
| Publicação | Diário Oficial do Estado — MG (referência típica **23/12/2025**; confirmar edição DOE da data) |
| Vigência dos preços (efeitos) | **1º de janeiro de 2026** a **30 de junho de 2026** |
| HTML (preâmbulo) | `https://www.fazenda.mg.gov.br/empresas/legislacao_tributaria/portarias/2025/port_saif062_2025.html` |
| PDF (anexos / tabelas PMPF) | `https://www.fazenda.mg.gov.br/empresas/legislacao_tributaria/portarias/2025/port_saif062_2025_anexos.pdf` |

Objeto (resumo): ICMS/ST — PMPF para refrigerantes e bebidas hidroeletrolíticas (isotônicas) ou energéticas.

## Onde está cada anexo no PDF

Extraído do conteúdo textual do PDF oficial (`pdfplumber`):

- **Anexo I — Refrigerantes**: início **página 1** do ficheiro `port_saif062_2025_anexos.pdf`; repetido em cada página do anexo no cabeçalho «ANEXO I - REFRIGERANTES». Na **primeira página**, a linha de cabeçalho da tabela inclui as colunas «ITEM», «EMBALAGEM», «MARCA», «CÓDIGO DO FABRICANTE», «PMPF» (layout com células mescladas — ver código).
- **Anexo II — Bebidas hidroeletrolíticas**: a partir da **página 17** (cabeçalho «ANEXO II»).
- **Anexo III — Bebidas energéticas**: a partir da **página 18** (cabeçalho «ANEXO III»).

Os números de página referem-se ao PDF ligado acima na data da última actualização deste repositório.

## Dicionário `ANEXO_NCM_MG` (código)

Definido em `sefaz_mg_pdf_parser.py`:

| Anexo | Produto (título no PDF) | NCM atribuído | Notas |
| ----- | ------------------------ | ------------- | ----- |
| I | Refrigerantes | **22021000** | Entregável principal; refrigerantes com teor de açúcar / águas gaseificadas adicionadas de açúcar — NCM de referência para ST MG conforme linha de produtos do anexo. |
| II | Bebidas hidroeletrolíticas | **22021000** | Placeholder alinhado ao pedido inicial; **confirmar** se na política de substituição tributária da UF o item deve usar capítulo/precoito diferente (ex.: outros sob 2202.99). |
| III | Bebidas energéticas | **22021000** | Idem — rever quando estes anexos forem importados no pipeline. |

Qualquer alteração ao NCM deve citar ato infralegal MG ou posição fiscal defendável e actualizar testes + este ficheiro.

## Alíquota interna

Na ausência de coluna de alíquota nas tabelas do PDF, o parser usa **18%** (`0.18`), coerente com modulação usual do ICMS-MG em operações abrangidas — ver **RICMS-MG** e PG das decisões normativas vigentes.

## Importação

- Identificador de parser sugerido: `importado_por = sefaz_mg_pdf_parser_v1`.
- Primeira importação sugerida: apenas **Anexo I** (`apenas_anexos={"I"}`).
- Após importar para `tabela_pmpf`, validar na BD pelo menos um registo com `estado = MG`, `nivel_confianca_fonte = candidata_oficial`, `ncm` preenchido (script CLI faz dry-run e sugere verificação SQL).

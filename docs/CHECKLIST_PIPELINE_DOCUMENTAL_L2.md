# CHECKLIST — Pipeline Documental L2

**Criado:** 2026-05-11  

**Princípio:** documento do utilizador nunca sai da plataforma

## Fronteira arquitectural confirmada

- `pdf_report_service.py` = emissor (saída da plataforma) — NÃO tocar

- `sefaz_mg_pdf_parser.py` = leitor normativo oficial — NÃO tocar

- `document_ingestion/` = novo domínio — a construir

## Dependências

- [x] `pdfplumber==0.11.9` — já em requirements.txt

- [x] `pillow==12.1.1` — já em requirements.txt

- [ ] `pytesseract` — adicionar só quando OCR existir em código

- [ ] Binário Tesseract no container Railway — a configurar

## Política de confiança

| Score OCR | Acção |

|-----------|-------|

| ≥ 95% | Auto-processa → motor fiscal |

| 70–94% | Aceita com aviso — regista incerteza no ledger |

| < 70% | Rejeita — pede documento melhor ao utilizador |

## Tipos de documento suportados (V1)

- [ ] PDF digital (texto extraível — pdfplumber)

- [ ] PDF scan (imagem — pytesseract)

- [ ] Imagem (JPEG/PNG — pillow + pytesseract)

- [ ] DANFE (PDF estruturado — parser dedicado)

## Estrutura a criar

- [ ] `app/services/document_ingestion/__init__.py`

- [ ] `app/services/document_ingestion/classifier.py`

- [ ] `app/services/document_ingestion/extractor.py`

- [ ] `app/services/document_ingestion/confidence.py`

- [ ] `app/services/document_ingestion/normalizer.py`

- [ ] `app/services/document_ingestion/audit.py`

## Migration

- [ ] `migrations/versions/0004_create_documentos_ingeridos.py`

## Testes

- [ ] `tests/test_document_ingestion.py`

- [ ] Teste rejeição < 70% confiança

- [ ] Teste auto-processo ≥ 95%

- [ ] Teste documento degradado

## Contador parceiro

- [ ] Documentos com 70–94% confiança → fila homologação contador

- [ ] Contador assina digitalmente resultado — não corrige motor

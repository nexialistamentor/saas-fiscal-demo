"""B02 C1-only: PDF pagination regression with synthetic documents.

A generated PDF with 587 pages is NOT a SEFA/PR source or a RuleVersion.
Actual source bytes are checked separately and never used as fake ADR020 rows.
"""
from __future__ import annotations
import copy
import hashlib
from io import BytesIO
from pathlib import Path
import importlib.util
import unittest

from pypdf import PdfReader, PdfWriter
from tools.enterprise_g113_exact_normative_excerpt import G113EvidenceError

BASE=Path(__file__).resolve().parent / 'test_enterprise_g113_exact_normative_excerpt.py'
spec=importlib.util.spec_from_file_location('_b02_existing_c1_fixture', BASE)
existing=importlib.util.module_from_spec(spec)
spec.loader.exec_module(existing)


class TestB02C1Pages(unittest.TestCase):
    """Uses the EXISTING C1 test fixture unchanged and the real C1 function."""

    def setUp(self):
        self.original=existing.G113Synthetic(methodName='test_01_genuine_synthetic_page_rule_item_bridge_noncommercial')
        self.original.setUp()

    def make_case(self, count: int, position: int):
        src=PdfReader(BytesIO(self.original.pdf),strict=True)
        writer=PdfWriter()
        for number in range(1,count+1):
            if number==position:
                writer.add_page(src.pages[0])
            else:
                writer.add_blank_page(width=595,height=842)
        target=BytesIO();writer.write(target);raw=target.getvalue()
        obj=self.original
        obj.pdf=raw
        obj.digest=hashlib.sha256(raw).hexdigest()
        target_reader=PdfReader(BytesIO(raw),strict=True)
        self.assertEqual(len(target_reader.pages),count)
        text=target_reader.pages[position-1].extract_text(extraction_mode='plain')
        self.assertEqual(text.count(existing.QUOTATION),1)
        anchor=obj.e.evidence['g113_v1']
        anchor['pdf_sha256']=obj.digest
        anchor['pagina_1_based']=position
        anchor['pagina_texto_sha256']=hashlib.sha256(text.encode('utf-8')).hexdigest()
        anchor['inicio_caracter']=text.index(existing.QUOTATION)
        obj.r.evidence['g113_v1']=copy.deepcopy(anchor)
        obj.e.artifact_hash=obj.digest
        obj.g14['sha256_texto_normativo_declarado']=obj.digest
        obj.g18['itens'][0]['sha256_publicacao_observado']=obj.digest
        return obj

    def test_01_587_paginas_aceites_pagina_55_sem_promocao(self):
        r=self.make_case(587,55).audit()
        self.assertEqual(r['pagina_1_based'],55)
        self.assertTrue(r['excerto_presente_nos_bytes_pdf_extraidos'])
        self.assertIs(r['autoridade_fiscal'],False)
        self.assertIs(r['fonte_primaria_autenticada'],False)
        self.assertIs(r['credito_confirmado'],False)
        self.assertIs(r['checkout_autorizado'],False)
        self.assertIs(r['prova_de_relacao_semantica_entre_excerto_e_parametros'],False)

    def test_02_587_paginas_aceites_pagina_86(self):
        r=self.make_case(587,86).audit()
        self.assertEqual(r['pagina_1_based'],86)

    def test_03_587_paginas_aceites_ultima_pagina(self):
        r=self.make_case(587,587).audit()
        self.assertEqual(r['pagina_1_based'],587)

    def test_04_600_paginas_aceites_limite_exato(self):
        r=self.make_case(600,600).audit()
        self.assertEqual(r['pagina_1_based'],600)

    def test_05_601_paginas_bloqueadas(self):
        o=self.make_case(601,1)
        with self.assertRaisesRegex(G113EvidenceError,'G113_PAGINA_FORA_DO_DOCUMENTO'):
            o.audit()

    def test_06_hash_pdf_mutado_bloqueado(self):
        o=self.make_case(587,55)
        with self.assertRaisesRegex(G113EvidenceError,'G113_PDF_BYTES_OU_HASH_INVALIDOS'):
            o.audit(pdf_bytes=o.pdf+b' ')

    def test_07_hash_pagina_diferente_bloqueado(self):
        o=self.make_case(587,55)
        o.e.evidence['g113_v1']['pagina_texto_sha256']='0'*64
        o.r.evidence=copy.deepcopy(o.e.evidence)
        with self.assertRaisesRegex(G113EvidenceError,'G113_PAGINA_TEXTO_DIVERGENTE'):
            o.audit()

    def test_08_offset_diferente_bloqueado(self):
        o=self.make_case(587,55)
        o.e.evidence['g113_v1']['inicio_caracter']+=1
        o.r.evidence=copy.deepcopy(o.e.evidence)
        with self.assertRaisesRegex(G113EvidenceError,'G113_EXCERTO_NAO_UNICO_OU_OFFSET_DIVERGENTE'):
            o.audit()

    def test_09_arquivo_nao_pode_ser_substituido_por_pdf_distinto(self):
        o=self.make_case(587,55)
        old=o.digest
        replacement=o.pdf+b' '
        new=hashlib.sha256(replacement).hexdigest()
        with self.assertRaises(G113EvidenceError):
            o.audit(pdf_bytes=replacement,pdf_sha256=new)
        self.assertNotEqual(old,new)

    def test_10_c1_indice_1_em_587(self):
        r=self.make_case(587,1).audit()
        self.assertEqual(r['pagina_1_based'],1)

    def test_11_outro_item_nao_pode_reutilizar_prova(self):
        o=self.make_case(587,55)
        o.g14['indice_item']=2
        with self.assertRaises(G113EvidenceError):
            o.audit()

    def test_12_vigencia_declarada_nao_e_vigencia_comprovada(self):
        r=self.make_case(587,55).audit()
        for k in ('vigencia_juridica_comprovada','formula_juridicamente_autorizada',
                  'atualizacao_e_revogacao_exaustivas','usavel_comercialmente'):
            self.assertIs(r[k],False)

if __name__=='__main__':unittest.main()

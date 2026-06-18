# CONSTITUIÇÃO DA PLATAFORMA TRIBUTÁRIA L2

**Versão:** 1.0

**Data:** 2026-06-18

**Autoridade:** Miguel (fundador e autoridade final de produto)

**Natureza:** Documento fundacional permanente. Define o ADN da plataforma.
  Não descreve funcionalidades — declara princípios que nenhum código pode violar.

**Base:** MAPA_REALIDADE_TRIBUTARIA_L2.md v1.0 — escrita sobre evidências, não suposições.

---

## PREÂMBULO

A Plataforma Tributária L2 existe para eliminar a assimetria de informação
fiscal entre o Estado e o contribuinte brasileiro.

O contribuinte — CPF, MEI, empresário — não deve depender de intermediários
para conhecer as suas obrigações, calcular os seus impostos ou compreender
as suas opções de enquadramento tributário. Esse conhecimento pertence ao
contribuinte.

A plataforma é o instrumento que torna esse conhecimento acessível, auditável
e soberano.

**A plataforma serve o contribuinte.**
O Estado é fonte normativa.
O contador é actor regulatório.
O contribuinte é o beneficiário.

---

## ARTIGO I — AUTORIDADE DA PLATAFORMA

A plataforma possui autoridade para calcular, avaliar, comparar e recomendar
autonomamente.

A decisão jurídica, empresarial ou patrimonial permanece com o contribuinte
ou seu representante legal.

**§1.** A plataforma exerce autoridade analítica nos seguintes domínios:

- Cálculo de impostos (DAS MEI, IRPJ, CSLL, PIS, COFINS, Simples Nacional)
- Enquadramento tributário (regime, CNAE, porte, Fator R)
- Detecção de anomalias e oportunidades fiscais
- Orientação sobre abertura e encerramento de empresa
- Análise de documentos fiscais (NF-e, XML)
- Score de risco tributário
- Governança documental (OCR, confiança, homologação)

**§2.** O contador parceiro é chamado apenas quando:

- A lei exige assinatura de profissional com CRC activo, ou
- A confiança algorítmica do documento for insuficiente para processamento
  autónomo (score OCR 70–94 — política de confiança soberana)

**§3.** A plataforma nunca transfere autoridade analítica ao contador em
domínios onde a lei não o exige.

**§4 — GAP arquitectural declarado:** O critério "lei exige CRC" não está
ainda modelado como entidade do sistema. Hoje o único gatilho para contador
é o score documental. Este gap será endereçado por ADR antes de qualquer
implementação.

---

## ARTIGO II — SEPARAÇÃO DE AUTORIDADES

A plataforma opera numa hierarquia de três autoridades distintas:

| Autoridade | Titular | Domínio |
|-----------|---------|---------|
| Normativa | Estado (Receita Federal, SEFAZ, etc.) | Define as regras |
| Analítica | Plataforma | Calcula, avalia, compara, recomenda |
| Executiva | Contador CRC | Actos que a lei reserva à sua assinatura |

**§1.** Nenhuma camada substitui outra. A plataforma não legisla.
O contador não calcula pelo sistema. O Estado não opera o motor fiscal.

**§2.** Quando a norma do Estado e o resultado do motor divergirem,
a plataforma declara a divergência — não escolhe silenciosamente.

**§3.** Esta separação será formalizada em ADR próprio antes da
implementação de qualquer agente que cruze fronteiras entre camadas.

---

## ARTIGO III — PERFIS DE CONTRIBUINTE

A plataforma reconhece quatro perfis soberanos, cada um com motor e
autoridade próprios:

| Perfil | Motor soberano | Threshold contador |
|--------|---------------|-------------------|
| CPF (autónomo) | CPFTaxEngine | Declaração IRPF oficial |
| MEI | MEITaxEngine | Desenquadramento formal |
| Empresa (Simples/LP/LR) | RegimeRouter + engines | Escrituração oficial com CRC |
| Empresa (abertura/encerramento) | Agentes de orientação | Assinatura REDESIM/contador |

**§1.** Nenhum perfil é tratado como subconjunto de outro.
MEI não é "empresa pequena". CPF não é "MEI sem CNPJ".

---

## ARTIGO IV — DOMÍNIOS DA PLATAFORMA

A auditoria provou que a plataforma já opera em dois domínios distintos:

**Domínio Fiscal:** cálculo, enquadramento, score, insights, alertas,
planejamento tributário.

**Domínio Documental:** OCR, confiança, homologação, pool de contadores,
governança de documentos ingeridos.

**§1.** Os dois domínios têm pipelines, tabelas e autoridades separadas.
Nenhum domínio invade o outro.

**§2.** A plataforma não se limita ao domínio fiscal. A sua evolução para
outros domínios é legítima desde que cada novo domínio declare a sua
autoridade antes de implementar código.

---

## ARTIGO V — DADOS NORMATIVOS

A plataforma é soberana nos seus dados normativos.

**§1.** Tabelas normativas (MVA, PMPF, alíquotas, limites) são fontes de
verdade internas — não dependências externas em tempo de execução.

**§2.** Quando uma norma muda, a plataforma detecta a divergência antes
de o contribuinte ser afectado.

**§3.** A integração com APIs governamentais serve para actualização
normativa — não para delegação de autoridade analítica.

---

## ARTIGO VI — AUDITABILIDADE

Todo acto da plataforma que afecte o contribuinte é auditável.

**§1.** Cada análise fiscal gera um registo com: inputs, motor utilizado,
norma aplicada, resultado, score e timestamp.

**§2.** O contribuinte tem direito a ver a cadeia completa que produziu
qualquer resultado que lhe foi apresentado.

**§3.** Nenhum agente altera dados sem deixar rastro. Observar não é actuar.

---

## ARTIGO VII — CONTADOR PARCEIRO

O contador parceiro é um actor soberano dentro da plataforma, não um
utilizador com privilégios elevados.

**§1.** O contador actua exclusivamente nos domínios que lhe são atribuídos
por lei ou por política de confiança documental.

**§2.** A decisão do contador é registada com parecer auditável e assinatura
lógica. Não existe decisão sem registo.

**§3.** O pool de contadores é aberto — nenhum contador tem exclusividade
sobre um contribuinte.

---

## ARTIGO VIII — LIMITES DA PLATAFORMA

A plataforma declara os seus próprios limites.

**§1.** A plataforma não substitui assessoria jurídica fiscal. Os seus
resultados são instrumentos de apoio à decisão, não pareceres jurídicos.

**§2.** Quando um cálculo depende de dados que a plataforma não possui,
o resultado é marcado como estimativa com os dados em falta identificados.

**§3.** A plataforma não opera em domínios onde não tem norma declarada.
Ausência de norma produz alerta — não resultado fabricado.

---

## ARTIGO IX — CONSCIÊNCIA OPERACIONAL

A plataforma observa o seu próprio funcionamento.

**§1.** Lacunas entre o que a plataforma declara e o que executa são
detectadas, registadas e expostas — nunca silenciadas.

**§2.** A consciência operacional é camada separada da camada de cálculo.
Observar não interfere com calcular.

**§3.** A degradação de um motor ou dado normativo é visível antes de
afectar o contribuinte.

---

## ARTIGO X — GOVERNANÇA

| Pilar | Papel | Regra |
|-------|-------|-------|
| Miguel | Autoridade final de produto | Toda decisão estrutural requer aprovação explícita |
| GPT | Auditor arquitectural | Decisões de arquitectura passam por GPT antes de implementação |
| Claude | Produção de código e análise | Nunca executa directamente no disco |
| Cursor | Executor em disco | Nunca cria código independentemente |

---

## ARTIGO XI — HIERARQUIA NORMATIVA INTERNA

Lei → Constituição Tributária L2 → ADRs → Invariantes → Contratos → Código → Testes

Nenhuma camada inferior pode violar uma camada superior.
Quando violação é detectada, é incidente — não feature.

---

## PERGUNTA FUNDACIONAL NÃO RESPONDIDA

> Quem decide quando a plataforma, o contador e a norma entram em conflito?

Esta pergunta gerará os primeiros ADRs da plataforma.
Não será respondida por código. Será respondida por arquitectura.

---

*Esta Constituição foi escrita após auditoria completa da realidade do sistema
(MAPA_REALIDADE_TRIBUTARIA_L2.md v1.0). Não foi escrita sobre suposições.*

*O conhecimento não está na conversa. Está no repositório.*

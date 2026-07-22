# MISSION — Modelo Institucional

**Estado:** MODELO  
**Sistema:** Sistema de Construção Soberana  
**Documento superior:** CCS-001 — Constituição de Execução do Executor Técnico

---

# 1. Identificação

- ID
- Título
- Estado
- Data
- Autoridade emissora
- Executor
- Missão relacionada

---

# 2. Objetivo

Esta secção descreve, de forma objetiva e verificável, o resultado que a missão pretende alcançar.

Deve responder às seguintes perguntas:

- O que deve ser realizado?
- Porque esta missão existe?
- Qual o resultado esperado?
- Como será possível verificar que foi cumprida?

Não deve conter:

- instruções de implementação;
- decisões arquiteturais;
- opiniões;
- soluções técnicas específicas.

O Objetivo define apenas o resultado institucional esperado.

---

# 3. Escopo

Descreve exatamente os componentes autorizados para execução da missão.

Tudo o que não estiver explicitamente incluído no escopo considera-se fora da autorização.

---

# 4. Restrições

As restrições constituem limites obrigatórios da missão.

O Executor Técnico não pode violar qualquer restrição aqui definida.

## Restrições Gerais

- Não alterar ficheiros fora do escopo autorizado.
- Não modificar arquitetura.
- Não alterar contratos.
- Não alterar ADRs.
- Não alterar documentos constitucionais.
- Não introduzir dependências não autorizadas.
- Não criar funcionalidades adicionais.
- Não remover testes existentes.
- Não alterar comportamento público não previsto na missão.
- Não executar operações destrutivas sem autorização explícita.

## Restrições Operacionais

- Respeitar integralmente o CCS.
- Respeitar integralmente o AGENTS.md.
- Respeitar os ADRs ratificados.
- Produzir todas as evidências obrigatórias.
- Interromper imediatamente perante conflito institucional.

---

# 5. Entradas

As entradas identificam tudo o que o Executor Técnico pode utilizar durante a missão.

Nenhuma entrada fora desta lista deve ser assumida como disponível.

## Entradas possíveis

- Constituição (CCS)
- AGENTS.md
- ADRs referenciados
- Contratos institucionais
- Código-fonte existente
- Testes existentes
- Documentação existente
- Missão formal
- Evidências de missões anteriores (quando referenciadas)

## Restrições

O Executor Técnico não deve:

- assumir conhecimento externo não documentado;
- inferir requisitos não presentes na missão;
- utilizar memória de conversas anteriores como fonte institucional;
- criar dependências em informação não verificável.

Toda decisão deve ser fundamentada exclusivamente nas entradas autorizadas.

---

# 6. Saídas esperadas

As saídas representam todos os artefactos que devem existir ao término da missão.

A ausência de qualquer saída obrigatória impede a conclusão da missão.

## Saídas obrigatórias

- Implementação concluída (quando aplicável).
- Lista completa dos ficheiros alterados.
- Lista dos ficheiros criados.
- Lista dos ficheiros removidos.
- Evidências produzidas.
- Testes executados.
- Resultado dos testes.
- Limitações encontradas.
- Riscos identificados.
- Pendências identificadas.
- Estado final da missão.

## Estado final

A missão deve terminar exatamente num dos seguintes estados:

- CONCLUÍDA
- CONCLUÍDA COM PENDÊNCIAS
- INTERROMPIDA
- REJEITADA

Não são permitidos estados intermédios ou descrições livres.

---

# 7. Evidências obrigatórias

Toda missão deve produzir evidências suficientes para permitir a reprodução, auditoria e validação da execução.

## Evidências mínimas obrigatórias

- Estado inicial do repositório (`git status`).
- Lista dos ficheiros alterados.
- Diferenças produzidas (`git diff` ou equivalente).
- Testes executados.
- Resultado dos testes.
- Ferramentas utilizadas.
- Limitações encontradas.
- Riscos identificados.
- Estado final do repositório.

## Princípios

As evidências devem ser:

- verificáveis;
- reproduzíveis;
- objetivas;
- suficientes para auditoria independente.

A ausência de evidências obrigatórias impede a ratificação da missão.

---

# 8. Critérios de aceitação

Uma missão apenas pode ser considerada concluída quando todos os critérios abaixo forem satisfeitos.

## Critérios obrigatórios

- O objetivo definido na missão foi integralmente cumprido.
- O escopo autorizado foi respeitado.
- Nenhum componente fora do escopo foi alterado sem autorização.
- Todas as evidências obrigatórias foram produzidas.
- Todos os testes definidos na missão foram executados.
- Não existem regressões conhecidas introduzidas pela missão.
- O repositório permanece num estado consistente.

## Critérios de rejeição

A missão deve ser considerada não concluída quando ocorrer qualquer uma das seguintes situações:

- objetivo parcialmente cumprido;
- alteração de escopo;
- ausência de evidências;
- testes obrigatórios não executados;
- existência de regressões não justificadas;
- conflito com documentos institucionais superiores.

---

# 9. Critérios de interrupção

A execução deve ser interrompida imediatamente quando ocorrer qualquer uma das seguintes situações.

## Interrupção obrigatória

- A missão é ambígua.
- O escopo não pode ser determinado.
- Existe conflito entre documentos institucionais.
- É necessária uma decisão arquitetural.
- É necessária alteração de ADR.
- É necessária alteração de contrato.
- A implementação exige alterações fora do escopo autorizado.
- As evidências exigidas não podem ser produzidas.
- É identificada uma regressão que inviabiliza a continuidade da execução.

## Procedimento

O Executor Técnico não deve tomar decisões para contornar estas situações.

Deve:

1. interromper a execução;
2. registar o motivo no relatório;
3. preservar todas as evidências obtidas até ao momento;
4. devolver a missão ao Conselho de Arquitetura.

---

# 10. Relatório obrigatório

Toda missão concluída, interrompida ou rejeitada deve produzir um relatório institucional, elaborado de acordo com o modelo oficial de relatório do Sistema de Construção Soberana.

O relatório constitui a evidência formal da execução e é obrigatório para auditoria e ratificação.
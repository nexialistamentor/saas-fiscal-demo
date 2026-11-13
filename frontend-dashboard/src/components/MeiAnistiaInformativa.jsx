/**
 * SOLVERIS.MEI-ANISTIA-001 / Bloco 1 fail-closed.
 *
 * Orientação normativa de fonte oficial, sem consulta de dívidas por CNPJ,
 * soma de tributos, avaliação de elegibilidade ou solicitação de remissão.
 * Qualquer integração de débitos exige contrato próprio e nova ratificação.
 */
export default function MeiAnistiaInformativa() {
  return (
    <section className="card" aria-labelledby="mei-remissao-titulo"
      style={{ marginBottom: 20, overflowWrap: 'anywhere' }}>
      <h3 id="mei-remissao-titulo">Perdão de dívidas do MEI: entenda o que a lei prevê</h3>
      <p>
        A Lei Complementar nº 238/2026 prevê remissão dos débitos federais de
        contribuição previdenciária do MEI com vencimento até 13/10/2026,
        incluindo juros, multas e encargos. O perdão não abrange ICMS nem ISS.
      </p>
      <p>
        O processamento oficial começa em 01/01/2027. Para quem permanece
        enquadrado como MEI, é necessário manter em dia as contribuições
        dos seis meses seguintes. Dívidas discutidas judicialmente exigem
        procedimento específico de desistência conforme orientação da PGFN.
      </p>
      <p>
        Esta orientação tem caráter informativo: a SOLVERIS não consulta
        seus débitos individuais nesta tela nem realiza pedidos de remissão.
        Verifique os dados diretamente nos canais oficiais:
      </p>
      <nav aria-label="Fontes oficiais e consulta de débitos do MEI"
        style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 12 }}>
        <a href="https://www.regularize.pgfn.gov.br/" target="_blank" rel="noopener noreferrer">
          Consultar dívida ativa na PGFN
        </a>
        <a href="https://servicos.receitafederal.gov.br/" target="_blank" rel="noopener noreferrer">
          Consultar pendências na Receita Federal
        </a>
        <a href="https://www.gov.br/pgfn/pt-br/servicos/perguntas-frequentes/perguntas-frequentes-perdao-do-mei"
          target="_blank" rel="noopener noreferrer">
          Conferir as regras oficiais da remissão
        </a>
      </nav>
    </section>
  )
}

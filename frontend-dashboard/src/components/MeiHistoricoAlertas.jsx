function dataLegivel(value) {
  if (!value) return "Data indisponível"
  const data = new Date(value)
  return Number.isNaN(data.getTime()) ? "Data indisponível" : data.toLocaleString("pt-BR")
}

export default function MeiHistoricoAlertas({ analises, alertas, loading, erro, atualizar }) {
  return (
    <section className="card" aria-labelledby="mei-historico-title" style={{ marginBottom: 20, overflowWrap: "anywhere" }}>
      <h3 id="mei-historico-title">Histórico e alertas do seu MEI</h3>
      <p>Dados das análises registradas na SOLVERIS. Estes registros não comprovam quitação de tributos nem situação fiscal regular.</p>
      <button type="button" onClick={atualizar} disabled={loading}>Atualizar histórico e alertas</button>
      <div role="status" aria-live="polite">{loading && <p>Carregando histórico e alertas...</p>}</div>
      {erro && <p role="alert">{erro}</p>}
      {!loading && !erro && (
        <>
          <h4>Histórico de análises</h4>
          {analises.length === 0 ? <p>Nenhuma análise registrada. Ainda não há dados suficientes para acompanhar seu MEI.</p> : (
            <ul>{analises.map(item => (
              <li key={item.id}>Análise #{item.id} — {item.status} — {dataLegivel(item.data)}</li>
            ))}</ul>
          )}
          <h4>Alertas registrados</h4>
          {alertas.length === 0 ? <p>Nenhum alerta registrado. Isso não confirma ausência de pendências fiscais.</p> : (
            <ul>{alertas.map(item => (
              <li key={item.id}><strong>{item.nivel}</strong>: {item.descricao} — {dataLegivel(item.data)}</li>
            ))}</ul>
          )}
        </>
      )}
    </section>
  )
}

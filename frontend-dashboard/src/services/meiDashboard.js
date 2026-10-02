// Reads metadata and alerts only; never infers tax settlement or commercial access.
export function criarLeitorDashboardMei({ baseUrl, fetchAutenticado, onState }) {
  let sequence = 0
  let controller = null

  function invalidar() {
    sequence += 1
    controller?.abort()
    controller = null
  }

  async function carregar({ empresaId, enabled }) {
    invalidar()
    const ticket = sequence
    const valido = enabled === true && Number.isInteger(empresaId) && empresaId > 0
    const vazio = { empresaId, analises: [], alertas: [], loading: false, erro: "" }
    if (!valido) { onState(vazio); return }
    onState({ ...vazio, loading: true })
    const requestController = new AbortController()
    controller = requestController
    const signal = requestController.signal
    const timeout = setTimeout(() => requestController.abort(), 15000)
    try {
      const respostas = await Promise.all([
        fetchAutenticado(`${baseUrl}/dashboard/analises/${empresaId}`, { method: "GET", cache: "no-store", signal }),
        fetchAutenticado(`${baseUrl}/dashboard/alertas/${empresaId}`, { method: "GET", cache: "no-store", signal }),
      ])
      if (respostas.some(res => !res?.ok)) throw new Error("Dashboard indisponível")
      const [analises, alertas] = await Promise.all(respostas.map(res => res.json()))
      if (!Array.isArray(analises) || !Array.isArray(alertas)
          || analises.some(item => !item || !Number.isInteger(item.id) || item.id <= 0
            || typeof item.status !== "string")
          || alertas.some(item => !item || !Number.isInteger(item.id) || item.id <= 0
            || typeof item.descricao !== "string" || typeof item.nivel !== "string")) {
        throw new Error("Resposta do dashboard fora do contrato")
      }
      if (ticket === sequence) onState({ ...vazio, analises, alertas })
    } catch {
      if (ticket === sequence) onState({ ...vazio,
        erro: "Não foi possível carregar o histórico e os alertas. Tente atualizar." })
    } finally { clearTimeout(timeout); requestController.abort() }
  }

  return { carregar, invalidar }
}

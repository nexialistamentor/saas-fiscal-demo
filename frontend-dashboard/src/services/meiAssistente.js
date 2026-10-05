// Guided questions only: reuse the deterministic MEI branches of /perguntar.
export function prepararPerguntaMei({ tema, ano, faturamento, atividade }) {
  if (typeof ano !== 'string' || !/^20\d{2}$/.test(ano)) throw new Error('Informe um ano entre 2000 e 2099.')
  if (tema === 'limite') return { pergunta: `Qual o limite do MEI em ${ano}?`, tipo: 'mei_limit' }
  const atividades = { comercio: 'comércio', industria: 'indústria', servicos: 'serviços' }
  if (tema !== 'das' || !Object.hasOwn(atividades, atividade)
      || typeof faturamento !== 'string' || !/^\d{1,12}([.,]\d{1,2})?$/.test(faturamento)
      || Number(faturamento.replace(',', '.')) <= 0) {
    throw new Error('Informe faturamento mensal positivo e selecione a atividade.')
  }
  return { pergunta: `Como MEI de ${atividades[atividade]} em ${ano}, faturando R$ ${faturamento.replace(',', '.')} por mês, quanto pago de DAS?`, tipo: 'mei_tax' }
}

export function criarAssistenteMei({ baseUrl, fetchAutenticado, onState }) {
  let sequence = 0
  let controller = null
  const vazio = { loading: false, resultado: null, erro: '' }
  function invalidar() { sequence += 1; controller?.abort() }
  function limpar() { invalidar(); onState({ ...vazio }) }
  async function consultar({ empresaId, enabled, ...campos }) {
    invalidar()
    const ticket = sequence
    if (enabled !== true || !Number.isInteger(empresaId) || empresaId <= 0) {
      onState({ ...vazio }); return
    }
    let pergunta
    try { pergunta = prepararPerguntaMei(campos) }
    catch (erro) { onState({ ...vazio, erro: erro.message }); return }
    const requestController = new AbortController()
    controller = requestController
    const timer = setTimeout(() => requestController.abort(), 15000)
    onState({ ...vazio, loading: true })
    try {
      const res = await fetchAutenticado(`${baseUrl}/perguntar`, {
        method: 'POST', cache: 'no-store', signal: requestController.signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pergunta: pergunta.pergunta }),
      })
      if (!res?.ok) throw new Error('HTTP')
      const data = await res.json()
      if (!data || typeof data.resposta !== 'string' || !data.resposta.trim()
          || data.analysis_type !== pergunta.tipo || data.requires_payment !== false
          || ![null, undefined, false, true].includes(data.bloqueado)
          || (data.bloqueado === true && (data.estado_l3 !== 'bloqueado'
            || typeof data.tipo_bloqueio !== 'string' || !data.tipo_bloqueio.trim()))
          || (pergunta.tipo === 'mei_tax' && data.bloqueado !== true && data.modo !== 'estimativa')) {
        throw new Error('CONTRACT')
      }
      // No report, checkout, provider, HTML rendering or client-side tax calculation.
      if (ticket === sequence) onState({ ...vazio, resultado: {
        resposta: data.resposta, bloqueado: data.bloqueado === true,
        estimativa: pergunta.tipo === 'mei_tax' && data.bloqueado !== true,
      } })
    } catch {
      if (ticket === sequence) onState({ ...vazio, erro: 'Não foi possível obter a orientação. Verifique a sessão e tente novamente.' })
    } finally { clearTimeout(timer); requestController.abort() }
  }
  return { consultar, limpar, invalidar }
}

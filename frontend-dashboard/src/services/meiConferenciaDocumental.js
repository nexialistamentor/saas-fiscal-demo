function validar(body, empresaId, ano) {
  if (!body || body.empresa_id !== empresaId || body.ano_calendario !== ano
      || body.completude_anual_comprovada !== false || body.total_receita_confirmada !== null
      || !Array.isArray(body.receitas_confirmadas) || body.receitas_confirmadas.length
      || !Number.isInteger(body.duplicatas_ignoradas) || body.duplicatas_ignoradas < 0) throw Error('Contrato inválido')
  const ids = new Set()
  for (const campo of ['documentos_para_revisao', 'documentos_sem_periodo']) {
    if (!Array.isArray(body[campo])) throw Error('Contrato inválido')
    for (const item of body[campo]) {
      const m = item?.metadados
      if (!Number.isInteger(item?.documento_id) || item.documento_id <= 0 || ids.has(item.documento_id)
          || item.categoria_receita !== null || !m || m.id !== item.documento_id || m.empresa_id !== empresaId
          || !Array.isArray(item.motivos) || item.motivos.some(x => typeof x !== 'string' || !x)
          || !['EMITENTE_NAO_COMPROVADO', 'NATUREZA_OPERACAO_NAO_COMPROVADA', 'ESTADO_FISCAL_NAO_COMPROVADO'].every(x => item.motivos.includes(x))) throw Error('Documento inválido')
      if (campo === 'documentos_sem_periodo') {
        if (m.data_emissao !== null || !item.motivos.includes('PERIODO_NAO_COMPROVADO')) throw Error('Período inválido')
      } else if (typeof m.data_emissao !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(m.data_emissao)
          || Number(m.data_emissao.slice(0, 4)) !== ano
          || new Date(m.data_emissao + 'T00:00:00Z').toISOString().slice(0, 10) !== m.data_emissao) throw Error('Período inválido')
      if (m.valor_total !== null && (typeof m.valor_total !== 'number' || !Number.isFinite(m.valor_total) || m.valor_total < 0)) throw Error('Valor inválido')
      if (m.tipo !== null && !['entrada', 'saida'].includes(m.tipo)) throw Error('Tipo inválido')
      ids.add(item.documento_id)
    }
  }
  return body
}
export function criarLeitorConferenciaDocumentalMei({ baseUrl, fetchAutenticado, onState }) {
  let sequence = 0, controller = null
  function invalidar() { sequence++; controller?.abort(); controller = null }
  async function carregar({ empresaId, anoCalendario, enabled }) {
    invalidar()
    const ticket = sequence
    const vazio = { empresaId, anoCalendario, loading: false, resultado: null, erro: '' }
    if (enabled !== true || !Number.isInteger(empresaId) || empresaId <= 0 || !Number.isInteger(anoCalendario)
        || anoCalendario < 1900 || anoCalendario > 9999) { onState(vazio); return }
    onState({ ...vazio, loading: true })
    const request = new AbortController(); controller = request
    const timeout = setTimeout(() => request.abort(), 15000)
    try {
      const response = await fetchAutenticado(`${baseUrl}/dashboard/mei/${empresaId}/conferencia-documental?ano_calendario=${anoCalendario}`, { method: 'GET', cache: 'no-store', signal: request.signal })
      if (!response?.ok) throw Error('Indisponível')
      const resultado = validar(await response.json(), empresaId, anoCalendario)
      if (ticket === sequence) onState({ ...vazio, resultado })
    } catch {
      if (ticket === sequence) onState({ ...vazio, erro: 'Não foi possível carregar os documentos. Atualize ou entre novamente se a sessão expirou.' })
    } finally { clearTimeout(timeout); request.abort() }
  }
  return { carregar, invalidar }
}

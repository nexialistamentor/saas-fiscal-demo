const categorias = ['comercio_industria', 'servicos']
const identidade = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
function recusar() { throw Error('Contrato de receitas inválido') }
function centavos(value, agregado = false) {
  const pattern = agregado ? /^(?:0|[1-9][0-9]{0,17})\.[0-9]{2}$/ : /^(?:0|[1-9][0-9]{0,12})\.[0-9]{2}$/
  if (typeof value !== 'string' || !pattern.test(value)) recusar()
  return BigInt(value.replace('.', ''))
}
function chaves(value, esperadas) {
  if (!value || typeof value !== 'object' || Array.isArray(value)
      || Object.keys(value).length !== esperadas.length
      || !esperadas.every(key => Object.hasOwn(value, key))) recusar()
}
function validarApuracao(body, empresaId, anoCalendario) {
  chaves(body, ['empresa_id', 'ano_calendario', 'completude_anual_comprovada',
    'total_receitas_incluidas', 'totais_por_categoria', 'totais_por_origem',
    'meses', 'receitas_incluidas', 'pendencias', 'duplicatas_ignoradas'])
  if (body.empresa_id !== empresaId || body.ano_calendario !== anoCalendario
      || body.completude_anual_comprovada !== false || body.duplicatas_ignoradas !== 0
      || !Array.isArray(body.receitas_incluidas) || body.receitas_incluidas.length > 100000
      || !Array.isArray(body.pendencias) || body.pendencias.length !== 0
      || !Array.isArray(body.meses) || body.meses.length !== 12) recusar()
  chaves(body.totais_por_categoria, categorias)
  chaves(body.totais_por_origem, ['documento', 'informada_sem_nota'])
  const ids = new Set(), mensais = Array(12).fill(null)
  const porCategoria = { comercio_industria: 0n, servicos: 0n }
  let total = 0n
  for (const item of body.receitas_incluidas) {
    chaves(item, ['identidade_receita', 'empresa_id', 'data_receita', 'valor', 'categoria', 'origem', 'estado'])
    if (item.empresa_id !== empresaId || typeof item.identidade_receita !== 'string'
        || !identidade.test(item.identidade_receita) || ids.has(item.identidade_receita)
        || item.origem !== 'informada_sem_nota' || item.estado !== 'vigente'
        || !categorias.includes(item.categoria) || typeof item.data_receita !== 'string'
        || !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(item.data_receita)
        || Number(item.data_receita.slice(0, 4)) !== anoCalendario
        || new Date(item.data_receita + 'T00:00:00Z').toISOString().slice(0, 10) !== item.data_receita) recusar()
    const valor = centavos(item.valor)
    const indice = Number(item.data_receita.slice(5, 7)) - 1
    total += valor; porCategoria[item.categoria] += valor
    mensais[indice] = (mensais[indice] ?? 0n) + valor
    ids.add(item.identidade_receita)
  }
  if (centavos(body.total_receitas_incluidas, true) !== total
      || centavos(body.totais_por_origem.documento, true) !== 0n
      || centavos(body.totais_por_origem.informada_sem_nota, true) !== total) recusar()
  for (const categoria of categorias) {
    if (centavos(body.totais_por_categoria[categoria], true) !== porCategoria[categoria]) recusar()
  }
  for (const [indice, mes] of body.meses.entries()) {
    chaves(mes, ['mes', 'estado', 'total_receitas_incluidas'])
    if (mes.mes !== indice + 1) recusar()
    if (mensais[indice] === null) {
      if (mes.estado !== 'nao_informado' || mes.total_receitas_incluidas !== null) recusar()
    } else if (mes.estado !== 'parcial'
        || centavos(mes.total_receitas_incluidas, true) !== mensais[indice]) recusar()
  }
  return body
}
export function criarLeitorReceitasInformadasMei({ baseUrl, fetchAutenticado, onState }) {
  let sequence = 0, controller = null
  function invalidar() { sequence++; controller?.abort(); controller = null }
  async function carregar({ empresaId, anoCalendario, enabled }) {
    invalidar()
    const ticket = sequence
    const vazio = { empresaId, anoCalendario, loading: false, resultado: null, erro: '' }
    if (enabled !== true || !Number.isSafeInteger(empresaId) || empresaId <= 0
        || !Number.isInteger(anoCalendario) || anoCalendario < 1900 || anoCalendario > 9999) {
      onState(vazio); return
    }
    onState({ ...vazio, loading: true })
    const request = new AbortController(); controller = request
    const timeout = setTimeout(() => request.abort(), 15000)
    try {
      const response = await fetchAutenticado(`${baseUrl}/dashboard/mei/${empresaId}/receitas-informadas?ano_calendario=${anoCalendario}`,
        { method: 'GET', cache: 'no-store', signal: request.signal })
      if (!response?.ok) throw Error('Indisponível')
      const resultado = validarApuracao(await response.json(), empresaId, anoCalendario)
      if (ticket === sequence && !request.signal.aborted) onState({ ...vazio, resultado })
    } catch {
      if (ticket === sequence) onState({ ...vazio,
        erro: 'Não foi possível carregar as receitas informadas. Atualize ou entre novamente se a sessão expirou.' })
    } finally { clearTimeout(timeout); request.abort() }
  }
  return { carregar, invalidar }
}

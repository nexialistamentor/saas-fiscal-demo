const uuid4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
function validarDados(dados) {
  if (!dados || typeof dados !== 'object' || Array.isArray(dados)
      || Object.keys(dados).length !== 3
      || !['data_receita', 'valor', 'categoria'].every(key => Object.hasOwn(dados, key))
      || typeof dados.valor !== 'string' || !/^(?:0|[1-9][0-9]{0,12})\.[0-9]{2}$/.test(dados.valor)
      || !['comercio_industria', 'servicos'].includes(dados.categoria)
      || typeof dados.data_receita !== 'string' || !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(dados.data_receita)
      || Number(dados.data_receita.slice(0, 4)) < 1900
      || new Date(dados.data_receita + 'T00:00:00Z').toISOString().slice(0, 10) !== dados.data_receita) throw Error('Dados inválidos')
  return { data_receita: dados.data_receita, valor: dados.valor, categoria: dados.categoria }
}
function iguais(a, b) {
  return a.data_receita === b.data_receita && a.valor === b.valor && a.categoria === b.categoria
}
export function criarGravadorReceitaInformadaMei({ baseUrl, fetchAutenticado, storage, usuarioId, randomUUID }) {
  const emCurso = new Set()
  function chave(empresaId) {
    if (!Number.isSafeInteger(usuarioId) || usuarioId <= 0
        || !Number.isSafeInteger(empresaId) || empresaId <= 0) throw Error('Escopo inválido')
    return `solveris.meiReceitaInformada.v1:${usuarioId}:${empresaId}`
  }
  function pendente({ empresaId }) {
    const raw = storage.getItem(chave(empresaId))
    if (raw === null) return null
    const value = JSON.parse(raw)
    if (!value || typeof value !== 'object' || Array.isArray(value)
        || Object.keys(value).length !== 4 || value.usuarioId !== usuarioId || value.empresaId !== empresaId
        || typeof value.identidade_receita !== 'string' || !uuid4.test(value.identidade_receita)) throw Error('Tentativa inválida')
    return { usuarioId, empresaId, identidade_receita: value.identidade_receita, dados: validarDados(value.dados) }
  }
  async function registrar({ empresaId, enabled, dados }) {
    let storageKey, attempt, canonical
    try {
      if (enabled !== true) throw Error('Desabilitado')
      storageKey = chave(empresaId)
      canonical = validarDados(dados)
      if (emCurso.has(storageKey)) return { estado: 'em_curso' }
      attempt = pendente({ empresaId })
      if (attempt && !iguais(attempt.dados, canonical)) throw Error('Tentativa pendente')
      if (!attempt) {
        const identity = randomUUID()
        if (typeof identity !== 'string' || !uuid4.test(identity)) throw Error('Identidade inválida')
        attempt = { usuarioId, empresaId, identidade_receita: identity, dados: canonical }
        storage.setItem(storageKey, JSON.stringify(attempt))
        const saved = pendente({ empresaId })
        if (!saved || saved.identidade_receita !== identity || !iguais(saved.dados, canonical)) throw Error('Persistência indisponível')
      }
    } catch {
      return { estado: 'bloqueado' }
    }
    emCurso.add(storageKey)
    const request = new AbortController()
    const timeout = setTimeout(() => request.abort(), 15000)
    try {
      const response = await fetchAutenticado(`${baseUrl}/dashboard/mei/${empresaId}/receitas-informadas`, {
        method: 'POST', cache: 'no-store', signal: request.signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...attempt.dados, identidade_receita: attempt.identidade_receita }),
      })
      if (!response?.ok) return { estado: [401, 403, 409, 422].includes(response?.status) ? 'bloqueado' : 'incerto' }
      const registro = await response.json()
      if (!registro || typeof registro !== 'object' || Array.isArray(registro)
          || Object.keys(registro).length !== 7 || !Number.isSafeInteger(registro.id) || registro.id <= 0
          || registro.empresa_id !== empresaId || registro.identidade_receita !== attempt.identidade_receita
          || registro.origem !== 'informada_sem_nota' || !iguais(registro, attempt.dados)) throw Error('Resposta divergente')
      // A failed cleanup keeps the original identity for a safe replay.
      storage.removeItem(storageKey)
      return { estado: 'salvo', registro }
    } catch {
      return { estado: 'incerto' }
    } finally {
      clearTimeout(timeout); request.abort(); emCurso.delete(storageKey)
    }
  }
  return { registrar, pendente }
}

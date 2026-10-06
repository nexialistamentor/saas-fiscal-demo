import { useEffect, useMemo, useState } from 'react'
import { API_BASE, fetchAutenticado } from '../config'
import { criarLeitorConferenciaDocumentalMei } from '../services/meiConferenciaDocumental'

const motivos = {
  EMITENTE_NAO_COMPROVADO: 'Emitente não comprovado',
  NATUREZA_OPERACAO_NAO_COMPROVADA: 'Natureza da operação não comprovada',
  ESTADO_FISCAL_NAO_COMPROVADO: 'Situação fiscal do documento não comprovada',
  PERIODO_NAO_COMPROVADO: 'Data de emissão ausente',
  TIPO_DOCUMENTAL_AUSENTE: 'Tipo documental ausente',
  VALOR_DOCUMENTAL_AUSENTE: 'Valor documental ausente',
  REFERENCIA_DOCUMENTAL_AUSENTE: 'Referência documental ausente',
}
const estadosEmitente = {
  coincidente: 'CNPJ coincide com o da empresa',
  divergente: 'CNPJ diverge do da empresa',
  ausente: 'CNPJ do emitente não informado',
  invalido: 'CNPJ observado fora do formato comparável',
  empresa_sem_cnpj_comparavel: 'Empresa sem CNPJ comparável',
}
function Documentos({ itens, observacoes = [] }) {
  const porDocumento = new Map(observacoes.map(item => [item.documento_id, item]))
  return <ul>{itens.map(item => <li key={item.documento_id}>
    <strong>Documento #{item.documento_id}</strong>
    <p>Emitente observado: {porDocumento.get(item.documento_id)?.cnpj_emitente_observado || 'não informado'}.
      {' '}{estadosEmitente[porDocumento.get(item.documento_id)?.estado] || 'Comparação do emitente indisponível'}.</p>
    <p>Emissão: {item.metadados.data_emissao || 'não informada'}. Valor registrado: {item.metadados.valor_total === null ? 'não informado' : item.metadados.valor_total.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}.</p>
    <p>{item.motivos.map(motivo => motivos[motivo] || 'Informação documental pendente').join('; ')}.</p>
  </li>)}</ul>
}
export default function MeiConferenciaDocumental({ empresaId }) {
  const [ano, setAno] = useState(String(new Date().getFullYear()))
  const [state, setState] = useState({ resultado: null, loading: false, erro: '' })
  const client = useMemo(() => criarLeitorConferenciaDocumentalMei({ baseUrl: API_BASE, fetchAutenticado, onState: setState }), [])
  const anoCalendario = /^\d{4}$/.test(ano) ? Number(ano) : NaN
  useEffect(() => {
    client.carregar({ empresaId, anoCalendario, enabled: true })
    return () => client.invalidar()
  }, [client, empresaId, anoCalendario])
  const resultado = state.empresaId === empresaId && state.anoCalendario === anoCalendario ? state.resultado : null
  return <section className="card" aria-labelledby="mei-conferencia-titulo" style={{ marginBottom: 20, overflowWrap: 'anywhere' }}>
    <h3 id="mei-conferencia-titulo">Documentos para conferência anual</h3>
    <p>Este inventário não comprova a receita anual completa. Os valores dos documentos ainda não são receitas confirmadas. A conferência automática dessas pendências ainda não está disponível.</p>
    <p>A comparação de CNPJ não comprova autenticidade nem confirma receita.</p>
    <label>Ano de referência <input type="number" min="1900" max="9999" step="1" value={ano} onChange={event => { client.invalidar(); setState({ resultado: null, loading: false, erro: '' }); setAno(event.target.value) }} /></label>
    <button type="button" disabled={state.loading || !Number.isInteger(anoCalendario) || anoCalendario < 1900 || anoCalendario > 9999} onClick={() => client.carregar({ empresaId, anoCalendario, enabled: true })}>Atualizar documentos</button>
    {state.loading && <p role="status">Carregando documentos...</p>}
    {state.erro && <p role="alert">{state.erro}</p>}
    {resultado && <>
      <h4>Documentos do ano selecionado</h4>
      {resultado.documentos_para_revisao.length ? <Documentos itens={resultado.documentos_para_revisao} observacoes={resultado.observacoes_emitente} /> : <p>Nenhum documento encontrado para este ano. Isso não significa receita anual zero.</p>}
      <h4>Documentos sem período comprovado</h4>
      {resultado.documentos_sem_periodo.length ? <Documentos itens={resultado.documentos_sem_periodo} observacoes={resultado.observacoes_emitente} /> : <p>Nenhum documento sem data encontrado.</p>}
    </>}
  </section>
}

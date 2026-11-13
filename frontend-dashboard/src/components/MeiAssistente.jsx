import { useEffect, useMemo, useState } from 'react'
import { API_BASE, fetchAutenticado } from '../config'
import { criarAssistenteMei } from '../services/meiAssistente'

export default function MeiAssistente({ empresaId }) {
  const [tema, setTema] = useState('limite')
  const [ano, setAno] = useState(String(new Date().getFullYear()))
  const [faturamento, setFaturamento] = useState('')
  const [atividade, setAtividade] = useState('')
  const [state, setState] = useState({ loading: false, resultado: null, erro: '' })
  const client = useMemo(() => criarAssistenteMei({ baseUrl: API_BASE, fetchAutenticado, onState: setState }), [])
  useEffect(() => () => client.invalidar(), [client])
  function editar(setter, value) { client.limpar(); setter(value) }
  function consultar(event) {
    event.preventDefault()
    if (state.loading) return
    client.consultar({ empresaId, enabled: true, tema, ano, faturamento, atividade })
  }
  return (
    <section className="card" style={{ marginBottom: 20 }} aria-labelledby="mei-assistente-titulo">
      <h3 id="mei-assistente-titulo">Assistente de orientação MEI</h3>
      <p>Orientação gratuita sobre limite e estimativa de DAS. Usa os dados que você informar; não consulta XMLs, débitos ou pagamentos da empresa e não comprova regularidade fiscal.</p>
      <p className="mei-limite-futuro-nota" style={{ fontSize: 13 }}>
        A Lei Complementar 238/2026 prevê R$ 110.000 para o ano-calendário 2027 e
        R$ 140.000 a partir de 2028. Esses limites estão condicionados à consideração da renúncia de receita na lei orçamentária de 2027 a 2029 (art. 3º).
        Sem comprovação dessa condição e fonte normativa internalizada, a SOLVERIS mantém bloqueada a consulta do limite futuro.
        Este aviso não substitui a consulta de limite aos canais oficiais.{' '}
        <a href="https://www2.camara.leg.br/legin/fed/leicom/2026/leicomplementar-238-21-outubro-2026-800071-publicacaooriginal-181678-pl.html"
          target="_blank" rel="noopener noreferrer">Confira a lei oficial</a>.
      </p>
      <form onSubmit={consultar} style={{ display: 'grid', gap: 12, maxWidth: 420 }}>
        <label>O que deseja saber?
          <select value={tema} onChange={e => editar(setTema, e.target.value)} disabled={state.loading}>
            <option value="limite">Limite de faturamento do MEI</option>
            <option value="das">Estimar DAS mensal</option>
          </select>
        </label>
        <label>Ano de referência
          <input type="number" min="2000" max="2099" step="1" required value={ano}
            onChange={e => editar(setAno, e.target.value)} disabled={state.loading} />
        </label>
        {tema === 'das' && <>
          <label>Faturamento mensal informado (R$)
            <input type="text" inputMode="decimal" maxLength={15} required value={faturamento}
              placeholder="Ex.: 6000,00" onChange={e => editar(setFaturamento, e.target.value)} disabled={state.loading} />
          </label>
          <label>Atividade
            <select required value={atividade} onChange={e => editar(setAtividade, e.target.value)} disabled={state.loading}>
              <option value="">Selecione</option><option value="comercio">Comércio</option>
              <option value="industria">Indústria</option><option value="servicos">Serviços</option>
            </select>
          </label>
        </>}
        <button type="submit" disabled={state.loading}>{state.loading ? 'Consultando orientação...' : 'Consultar gratuitamente'}</button>
      </form>
      <div role="status" aria-live="polite" style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
        {state.resultado && <>
          <p>{state.resultado.bloqueado ? 'Orientação bloqueada: faltam dados ou autoridade normativa.' : state.resultado.estimativa ? 'Estimativa informativa — não é DAS oficial.' : 'Orientação sobre o limite de faturamento.'}</p>
          <p>{state.resultado.resposta}</p>
        </>}
      </div>
      {state.erro && <p role="alert">{state.erro}</p>}
    </section>
  )
}

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { API_BASE, fetchAutenticado } from '../config'
import { criarLeitorReceitasInformadasMei } from '../services/meiReceitasInformadas'
import { criarGravadorReceitaInformadaMei } from '../services/meiReceitaInformadaGravacao'

const vazio = { data_receita: '', valor: '', categoria: 'servicos' }
const meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
function moeda(valor) {
  const [inteiro, centavos] = valor.split('.')
  return `R$ ${inteiro.replace(/\B(?=(\d{3})+(?!\d))/g, '.')},${centavos}`
}
const campo = { display: 'grid', gap: 6, minWidth: 0 }
const entrada = { width: '100%', minWidth: 0, boxSizing: 'border-box' }

export default function MeiReceitasInformadas({ empresaId, usuarioId }) {
  const [ano, setAno] = useState(String(new Date().getFullYear()))
  const [state, setState] = useState({ resultado: null, loading: false, erro: '' })
  const [salvando, setSalvando] = useState(false)
  const [mensagem, setMensagem] = useState('')
  const [erroGravacao, setErroGravacao] = useState('')
  const vivo = useRef(true), ocupado = useRef(false)
  const writer = useMemo(() => criarGravadorReceitaInformadaMei({
    baseUrl: API_BASE, fetchAutenticado, usuarioId,
    storage: {
      getItem: key => window.localStorage.getItem(key),
      setItem: (key, value) => window.localStorage.setItem(key, value),
      removeItem: key => window.localStorage.removeItem(key),
    },
    randomUUID: () => window.crypto.randomUUID(),
  }), [usuarioId, empresaId])
  const [recuperacao, setRecuperacao] = useState(() => {
    try { return { tentativa: writer.pendente({ empresaId }), erro: false } }
    catch { return { tentativa: null, erro: true } }
  })
  const [dados, setDados] = useState(() => recuperacao.tentativa?.dados || { ...vazio })
  const reader = useMemo(() => criarLeitorReceitasInformadasMei({
    baseUrl: API_BASE, fetchAutenticado, onState: setState,
  }), [])
  const anoCalendario = /^[0-9]{4}$/.test(ano) ? Number(ano) : NaN
  const escopo = { empresaId, anoCalendario, enabled: true }
  const resultado = state.empresaId === empresaId && state.anoCalendario === anoCalendario ? state.resultado : null
  useEffect(() => {
    vivo.current = true
    return () => { vivo.current = false; reader.invalidar() }
  }, [reader])
  useEffect(() => {
    reader.carregar({ empresaId, anoCalendario, enabled: true })
    return () => reader.invalidar()
  }, [reader, empresaId, anoCalendario])
  const pendente = Boolean(recuperacao.tentativa)
  function alterar(campo, value) {
    if (pendente || salvando || recuperacao.erro) return
    setDados(previous => ({ ...previous, [campo]: value }))
    setMensagem(''); setErroGravacao('')
  }
  async function registrar(event) {
    event?.preventDefault()
    if (ocupado.current || recuperacao.erro) return
    ocupado.current = true; setSalvando(true); setMensagem(''); setErroGravacao('')
    const enviados = { ...dados }
    try {
      const result = await writer.registrar({ empresaId, enabled: true, dados: enviados })
      if (!vivo.current) return
      let tentativa
      try { tentativa = writer.pendente({ empresaId }) }
      catch {
        setRecuperacao({ tentativa: null, erro: true })
        setErroGravacao('Não foi possível recuperar a tentativa. Não crie outro lançamento antes de conferir o registro.')
        return
      }
      setRecuperacao({ tentativa, erro: false })
      if (result.estado === 'salvo') {
        setDados({ ...vazio }); setMensagem('Receita registrada.')
        const anoReceita = String(Number(enviados.data_receita.slice(0, 4)))
        if (ano !== anoReceita) setAno(anoReceita)
        else await reader.carregar(escopo)
      } else if (result.estado === 'incerto') {
        setErroGravacao('A confirmação não chegou. Recupere o registro pendente com os mesmos dados; ele pode já ter sido salvo.')
      } else if (result.estado !== 'em_curso') {
        setErroGravacao(tentativa
          ? 'Não foi possível confirmar o registro. Preserve esta tentativa e confira a sessão e o acesso à empresa.'
          : 'Não foi possível registrar. Confira a data, o valor com duas casas decimais e a categoria; o armazenamento do navegador também precisa estar disponível.')
      }
    } finally {
      ocupado.current = false
      if (vivo.current) setSalvando(false)
    }
  }
  return <section className="card" aria-labelledby="mei-receitas-titulo"
    style={{ marginBottom: 20, padding: 16, overflowWrap: 'anywhere', minWidth: 0 }}>
    <h3 id="mei-receitas-titulo">Receitas sem nota informadas</h3>
    <p>Registre receitas sem nota e acompanhe os valores por mês e categoria. Os totais refletem somente os lançamentos informados e não comprovam a receita anual completa.</p>
    <p>Os documentos para conferência permanecem separados destes lançamentos. Este acompanhamento não confirma regularidade fiscal nem envia uma declaração.</p>
    {recuperacao.erro && <p role="alert">A tentativa anterior não pôde ser recuperada. Confira o registro antes de criar outro lançamento.</p>}
    {pendente && <p role="status">Há um registro pendente de confirmação. Os dados foram preservados para recuperar a mesma tentativa.</p>}
    <form onSubmit={registrar} style={{ display: 'grid', gap: 12, minWidth: 0 }}>
      <label style={campo}>Data da receita
        <input style={entrada} type="date" min="1900-01-01" max="9999-12-31" required
          disabled={pendente || salvando || recuperacao.erro} value={dados.data_receita}
          onChange={event => alterar('data_receita', event.target.value)} />
      </label>
      <label style={campo}>Valor da receita (R$)
        <input style={entrada} type="text" inputMode="decimal" placeholder="100.10" required
          pattern="(0|[1-9][0-9]{0,12})[.][0-9]{2}"
          disabled={pendente || salvando || recuperacao.erro} value={dados.valor}
          onChange={event => alterar('valor', event.target.value)} />
      </label>
      <p style={{ margin: 0 }}>Informe o valor com ponto e duas casas decimais, por exemplo: 100.10.</p>
      <label style={campo}>Categoria da receita
        <select style={entrada} disabled={pendente || salvando || recuperacao.erro} value={dados.categoria}
          onChange={event => alterar('categoria', event.target.value)}>
          <option value="servicos">Serviços</option>
          <option value="comercio_industria">Comércio e indústria</option>
        </select>
      </label>
      <button type="submit" disabled={salvando || recuperacao.erro}>
        {salvando ? 'Confirmando registro...' : pendente ? 'Recuperar registro pendente' : 'Registrar receita'}
      </button>
    </form>
    {mensagem && <p role="status">{mensagem}</p>}
    {erroGravacao && <p role="alert">{erroGravacao}</p>}
    <div style={{ display: 'grid', gap: 10, marginTop: 20 }}>
      <label style={campo}>Ano das receitas
        <input style={entrada} type="number" min="1900" max="9999" step="1" value={ano} disabled={salvando}
          onChange={event => { reader.invalidar(); setState({ resultado: null, loading: false, erro: '' }); setAno(event.target.value) }} />
      </label>
      <button type="button" disabled={state.loading || salvando || !Number.isInteger(anoCalendario) || anoCalendario < 1900 || anoCalendario > 9999}
        onClick={() => reader.carregar(escopo)}>Atualizar receitas</button>
    </div>
    {state.loading && <p role="status">Carregando receitas...</p>}
    {state.erro && <p role="alert">{state.erro}</p>}
    {resultado && <>
      {resultado.receitas_incluidas.length ? <>
        <p data-testid="receitas-total-parcial"><strong>Total parcial informado: {moeda(resultado.total_receitas_incluidas)}</strong></p>
        <p>Serviços: {moeda(resultado.totais_por_categoria.servicos)}. Comércio e indústria: {moeda(resultado.totais_por_categoria.comercio_industria)}.</p>
        <h4>Lançamentos do ano selecionado</h4>
        <ul>{resultado.receitas_incluidas.map(item => <li key={item.identidade_receita}>
          {item.data_receita} — {moeda(item.valor)} — {item.categoria === 'servicos' ? 'Serviços' : 'Comércio e indústria'} — informada sem nota.
        </li>)}</ul>
      </> : <><p>Nenhuma receita informada para este ano.</p><p>Isso não significa faturamento anual zero.</p></>}
      <h4>Acompanhamento mensal</h4>
      <ul>{resultado.meses.map(item => <li key={item.mes}>
        {meses[item.mes - 1]}: {item.estado === 'nao_informado' ? 'sem informação' : `${moeda(item.total_receitas_incluidas)} — parcial`}.
      </li>)}</ul>
    </>}
  </section>
}

import React, { useState, useEffect } from "react"
import "./App.css"
import useMeiDashboard from "./hooks/useMeiDashboard"
import useCpfDashboard from "./hooks/useCpfDashboard"
import useEmpresaDashboard from "./hooks/useEmpresaDashboard"
import RelatorioPDFButton from "./components/RelatorioPDFButton"
import {
  API_BASE,
  getToken,
  isAuthenticated,
  clearToken,
  login,
} from "./config"
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  Legend
} from "recharts"

const dadosNCM = [
  { nome: "3004", valor: 35 },
  { nome: "2203", valor: 20 },
  { nome: "8708", valor: 25 },
  { nome: "9403", valor: 20 }
]

function App() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [usuario, setUsuario] = useState(null)
  const [erroLogin, setErroLogin] = useState(null)
  const [verificandoSessao, setVerificandoSessao] = useState(true)

  const [mostrarRegisto, setMostrarRegisto] = useState(false)
  const [nomeRegisto, setNomeRegisto] = useState("")
  const [emailRegisto, setEmailRegisto] = useState("")
  const [passwordRegisto, setPasswordRegisto] = useState("")
  const [erroRegisto, setErroRegisto] = useState(null)
  const [sucessoRegisto, setSucessoRegisto] = useState(false)

  const perfilEmpresaApiRef = React.useRef(null)

  const [perfilAtual, setPerfilAtual] = React.useState({
    tipo: null,
    id: null,
    nome: ""
  })

  const perfisDisponiveis = React.useMemo(() => {
    const api = perfilEmpresaApiRef.current
    const lista = []
    if (api) {
      lista.push(api)
    } else {
      lista.push({ tipo: "empresa", id: null, nome: "Empresa" })
    }
    if (!api || api.tipo !== "mei") {
      lista.push({ tipo: "mei", id: null, nome: "MEI" })
    }
    lista.push({ tipo: "cpf", id: null, nome: "CPF" })
    return lista
  }, [perfilAtual])

  const tipoPerfil = perfilAtual.tipo
  const idPerfil = perfilAtual.id

  const [cpfFaturamentoMensal, setCpfFaturamentoMensal] = useState("")
  const [cpfDespesasMensais, setCpfDespesasMensais] = useState("")

  const meiResult = useMeiDashboard({
    faturamento_mensal: cpfFaturamentoMensal,
    despesas: cpfDespesasMensais
  })
  const cpfResult = useCpfDashboard({
    faturamento_mensal: cpfFaturamentoMensal,
    despesas: cpfDespesasMensais
  })
  const empresaResult = useEmpresaDashboard(
    tipoPerfil === "empresa" ? idPerfil : null
  )
  const { data, historico, tendencia, loading, risco, pontuacao, impacto, refetch } =
    tipoPerfil === "mei" ? meiResult :
    tipoPerfil === "cpf" ? cpfResult :
    empresaResult
  const severidadeRisco =
    risco >= 80 ? "crítico" :
    risco >= 60 ? "alto" :
    risco >= 40 ? "moderado" :
    risco >= 20 ? "baixo" :
    "controlado"
  const timelineFiscal =
    [...(historico ?? [])]
      .sort(
      (a, b) =>
        new Date(a?.data_snapshot ?? 0) -
        new Date(b?.data_snapshot ?? 0)
    )
      .map((item) => ({
      indice: item?.data_snapshot ? new Date(item.data_snapshot).getTime() : 0,
      data: item.data_snapshot
          ? new Date(item.data_snapshot).toLocaleDateString("pt-BR")
          : "data indisponível",
      score: item?.score_global ?? 0,
      risco: item?.risco_tributario ?? 0,
      maturidade: item?.maturidade_tributaria ?? 0
    })) ?? []
  const [checkoutLoading, setCheckoutLoading] = useState(false)
  const [checkoutErro, setCheckoutErro] = useState(null)
  const [resultadoXML, setResultadoXML] = useState(null)

  async function iniciarCheckout(e) {
    e.preventDefault()
    setCheckoutLoading(true)
    setCheckoutErro(null)
    try {
      const res = await fetch(`${API_BASE}/checkout/criar-pagamento`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${getToken()}`,
        },
        body: JSON.stringify({
          perfil_id: idPerfil,
          tipo_perfil: tipoPerfil,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || "Erro ao iniciar checkout.")
      }
      const { link_checkout } = await res.json()
      window.location.href = link_checkout
    } catch (err) {
      setCheckoutErro(err.message)
    } finally {
      setCheckoutLoading(false)
    }
  }

  const handleLogin = async (e) => {
    e.preventDefault()
    setErroLogin(null)

    try {
      await login(email, password)
      window.location.reload()
    } catch (err) {
      setErroLogin("Credenciais inválidas")
    }
  }

  const handleRegisto = async (e) => {
    e.preventDefault()
    setErroRegisto(null)

    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: emailRegisto,
          password: passwordRegisto,
          nome: nomeRegisto
        })
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || "Erro ao registar.")
      }

      setSucessoRegisto(true)
      await login(emailRegisto, passwordRegisto)
      window.location.reload()
    } catch (err) {
      setErroRegisto(err.message)
    }
  }

  function handleLogout() {
    clearToken()
    window.location.reload()
  }

  useEffect(() => {
    async function validarSessao() {
      if (!isAuthenticated()) {
        setVerificandoSessao(false)
        return
      }

      try {
        const res = await fetch(`${API_BASE}/auth/me`, {
          headers: {
            Authorization: `Bearer ${getToken()}`
          }
        })

        if (res.ok) {
          const usuarioJson = await res.json()
          setUsuario(usuarioJson)
          const er = await fetch(`${API_BASE}/empresas/`, {
            headers: { Authorization: `Bearer ${getToken()}` }
          })
          if (er.ok) {
            const list = await er.json()
            if (Array.isArray(list) && list.length > 0) {
              const e = list[0]

              const tipoDerivado = e.regime_tributario === "mei" ? "mei" : "empresa"

              const perfil = {
                tipo: tipoDerivado,
                id: e.id,
                nome:
                  e.regime_tributario === "mei"
                    ? `MEI - ${e.razao_social || `#${e.id}`}`
                    : e.razao_social || `Empresa #${e.id}`
              }
              perfilEmpresaApiRef.current = perfil
              setPerfilAtual(perfil)
            }
          }
        }

        if (!res.ok) {
          clearToken()
        }
      } catch {
        clearToken()
      }

      setVerificandoSessao(false)
    }

    validarSessao()
  }, [])

  const planoId = usuario?.plano_id ?? null
  const acessoBasico = planoId === 1
  const acessoPro = planoId === 2
  const acessoIlimitado = planoId === 3
  const podeUploadXML = acessoBasico || acessoPro || acessoIlimitado

  const historicoValido = historico.some((item) => (item.score_global ?? 0) > 0)

  const dadosEvolucao = historicoValido
    ? historico.map((item, index) => ({
        mes: item.data_snapshot ?? `P${index + 1}`,
        recuperacao: item.score_global ?? 0,
      }))
    : [
        { mes: "P1", recuperacao: 20 },
        { mes: "P2", recuperacao: 35 },
        { mes: "P3", recuperacao: 30 },
        { mes: "P4", recuperacao: 48 },
        { mes: "P5", recuperacao: 52 },
      ]

  useEffect(() => {
    if (!data?.consulta_paga) return
    if (!resultadoXML?.relatorio_id) return
    if (resultadoXML?.carregado) return

    carregarRelatorioSeguro(resultadoXML.relatorio_id)
  }, [data?.consulta_paga, resultadoXML?.relatorio_id, resultadoXML?.carregado])

  if (verificandoSessao) {
    return <p style={{ padding: 40 }}>Validando sessão...</p>
  }

  if (!isAuthenticated()) {
    return (
      <div style={{ padding: 40 }}>
        {!mostrarRegisto ? (
          <>
            <h2>Login</h2>

            <form onSubmit={handleLogin}>
              <input
                type="email"
                placeholder="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />

              <input
                type="password"
                placeholder="senha"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />

              <button type="submit">Entrar</button>

              {erroLogin && <p>{erroLogin}</p>}
            </form>

            <p style={{ marginTop: 16 }}>
              Não tem conta?{" "}
              <button
                type="button"
                onClick={() => setMostrarRegisto(true)}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  textDecoration: "underline"
                }}
              >
                Criar conta
              </button>
            </p>
          </>
        ) : (
          <>
            <h2>Criar conta</h2>

            <form onSubmit={handleRegisto}>
              <input
                type="text"
                placeholder="nome da empresa ou MEI"
                value={nomeRegisto}
                onChange={(e) => setNomeRegisto(e.target.value)}
              />

              <input
                type="email"
                placeholder="email"
                value={emailRegisto}
                onChange={(e) => setEmailRegisto(e.target.value)}
              />

              <input
                type="password"
                placeholder="senha"
                value={passwordRegisto}
                onChange={(e) => setPasswordRegisto(e.target.value)}
                aria-describedby="hint-password-registo"
                autoComplete="new-password"
              />
              <p
                id="hint-password-registo"
                style={{ margin: "4px 0 0", fontSize: 12, color: "#555" }}
              >
                Mínimo de 8 caracteres.
              </p>

              <button type="submit">Registar</button>

              {erroRegisto && <p>{erroRegisto}</p>}
            </form>

            <p style={{ marginTop: 16 }}>
              Já tem conta?{" "}
              <button
                type="button"
                onClick={() => setMostrarRegisto(false)}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  textDecoration: "underline"
                }}
              >
                Fazer login
              </button>
            </p>
          </>
        )}
      </div>
    )
  }

  if (loading) {
    return <p style={{ padding: 40 }}>Carregando dados fiscais...</p>
  }

  // Evita crash (#310): React não renderiza objetos como filhos de nós DOM.
  if (
    data !== null &&
    data !== undefined &&
    (typeof data !== "object" || Array.isArray(data))
  ) {
    return (
      <div style={{ padding: 40 }}>
        <p style={{ marginBottom: 12 }}>Debug — payload do mapa (formato inesperado):</p>
        <pre style={{ whiteSpace: "pre-wrap", fontSize: 12, background: "#f5f5f5", padding: 16 }}>
          {JSON.stringify(data, null, 2)}
        </pre>
      </div>
    )
  }

  function textoSeguro(value) {
    if (value == null) return "—"
    if (typeof value === "object") return JSON.stringify(value)
    return String(value)
  }

  const cardsDashboard = [
    {
      id: "restituicao-st",
      titulo: "Recuperação",
      valor: `R$ ${(data?.restituicao_st ?? 0).toLocaleString("pt-BR")}`,
    },
    {
      id: "risco-tributario",
      titulo: "Risco Tributário",
      valor: `${risco}%`,
    },
    {
      id: "severidade-risco",
      titulo: "Severidade",
      valor: severidadeRisco,
    },
    {
      id: "tendencia-inteligencia",
      titulo: "Tendência da Inteligência Fiscal",
      valor:
        tendencia?.tendencia === "melhoria_forte" || tendencia?.tendencia === "melhoria"
          ? "Melhoria"
          : tendencia?.tendencia === "queda_forte" || tendencia?.tendencia === "queda"
          ? "Queda"
          : tendencia?.tendencia === "estavel"
          ? "Estável"
          : "Insuficiente",
    },
    {
      id: "timeline-fiscal",
      titulo: "Eventos na Timeline",
      valor: timelineFiscal.length
        ? `${timelineFiscal.length} eventos (último: ${timelineFiscal[timelineFiscal.length - 1].data})`
        : "Sem eventos",
    },
    {
      id: "percepcoes-fiscais",
      titulo: "Percepções",
      valor: `${data?.total_insights ?? 0}`,
    },
    {
      id: "pontuacao-fiscal",
      titulo: "Pontuação Fiscal",
      valor: `${pontuacao}/100`,
    },
    {
      id: "estoque-fantasma",
      titulo: "Estoque Fantasma",
      valor: `${data?.estoque_fantasma ?? 0}`,
    },
  ]

  async function enviarXML(files) {
    const listaArquivos = Array.isArray(files) ? files.filter(Boolean) : [files].filter(Boolean)
    for (const file of listaArquivos) {
      const formData = new FormData()
      formData.append("file", file)
      formData.append("empresa_id", idPerfil)
      const resp = await fetch(`${API_BASE}/fiscal/analisar-xml?empresa_id=${idPerfil}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${getToken()}`
        },
        body: formData
      })
      const data = await resp.json()
      if (data.status === "finished" && data.result?.relatorio_id != null) {
        setResultadoXML({
          relatorio_id: data.result.relatorio_id,
          tem_resultado: data.result.tem_resultado,
          carregado: false
        })
        continue
      }
      if (data.job_id) {
        await new Promise((resolve) => {
          const intervalo = setInterval(async () => {
            const statusResp = await fetch(`${API_BASE}/fiscal/analise/status/${data.job_id}`, {
              headers: {
                Authorization: `Bearer ${getToken()}`
              }
            })
            const statusData = await statusResp.json()
            if (statusData.status === "finished") {
              clearInterval(intervalo)
              setResultadoXML({
                relatorio_id: statusData.result?.relatorio_id,
                tem_resultado: statusData.result?.tem_resultado,
                carregado: false
              })
              resolve()
            }
          }, 2000)
        })
      }
    }
    setTimeout(() => {
      refetch()
    }, 500)
  }

  async function carregarRelatorioSeguro(relatorio_id) {
    try {
      const res = await fetch(`${API_BASE}/relatorio/${relatorio_id}`, {
        headers: {
          Authorization: `Bearer ${getToken()}`
        }
      })

      const data = await res.json()

      if (data.status === "bloqueado") {
        return
      }

      setResultadoXML(prev => ({
        ...prev,
        dados: data,
        carregado: true
      }))
    } catch (e) {
      console.error("Erro ao carregar relatório seguro")
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="hero">
          <h1>Plataforma de Inteligência Tributária em Tempo Real</h1>
        </div>

        <button onClick={handleLogout}>Sair</button>
      </header>

      <div className="profile-toggle">
        {perfisDisponiveis.map((p) => (
          <button
            key={p.tipo}
            className={perfilAtual.tipo === p.tipo ? "active" : ""}
            onClick={() => setPerfilAtual(p)}
          >
            {p.nome}
          </button>
        ))}
      </div>
      {podeUploadXML && (
        <input  type="file"  accept=".xml"  multiple  onChange={(e) => enviarXML(Array.from(e.target.files ?? []))}/>
      )}

      {!podeUploadXML && (
        <div style={{ marginTop: 20 }}>
          <p>Upload de XML disponível apenas em planos superiores.</p>
        </div>
      )}

      {resultadoXML && !data?.consulta_paga && (
        <div style={{ marginTop: 20, padding: 20, border: "1px solid #ccc", borderRadius: 8 }}>
          <h3>Análise concluída</h3>
          <p>Seu XML foi processado com sucesso.</p>
          <p>Foram identificados elementos fiscais que podem compor um diagnóstico técnico.</p>
          <p>Desbloqueie o relatório completo para visualizar detalhes, fundamentos e valores recuperáveis.</p>
        </div>
      )}

      {resultadoXML?.carregado && data?.consulta_paga && (() => {
        const ra = resultadoXML.dados?.resultado ?? resultadoXML.dados
        const df = ra?.dados_fiscais
        return (
        <div style={{ marginTop: 20, padding: 20, border: "1px solid #ccc", borderRadius: 8 }}>
          <h3>Resultado da Análise XML</h3>

          <p><strong>Chave NF-e:</strong> {textoSeguro(df?.chave_nfe)}</p>
          <p><strong>CNPJ Emitente:</strong> {textoSeguro(df?.cnpj_emitente)}</p>
          <p><strong>Valor Nota:</strong> R$ {textoSeguro(df?.valor_total_nota)}</p>
          <p><strong>ICMS-ST:</strong> R$ {textoSeguro(df?.icms_st)}</p>

          <h4>Insights</h4>
          <ul>
            {(ra?.insights ?? []).map((i, idx) => (
              <li key={idx}>
                {typeof i === "string"
                  ? i
                  : textoSeguro(i?.descricao ?? i?.tipo ?? i)}
              </li>
            ))}
          </ul>

          <h4>Recuperação Estimada</h4>
          <p>
            R$ {textoSeguro(ra?.previsao_recuperacao?.potencial_recuperacao_nota)}
          </p>
        </div>
        )
      })()}

      <main className="dashboard">
        <section className="hero-card">
          <h2>Visão Geral</h2>
          <p>Acompanhe oportunidades, riscos e indicadores fiscais da empresa.</p>
        </section>

        {perfilAtual.tipo === "cpf" && (
          <section className="card" style={{ marginBottom: 20 }}>
            <h3>Dados para simulação CPF</h3>

            <div style={{ display: "grid", gap: 12, maxWidth: 420 }}>
              <label>
                <span>Faturamento mensal</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={cpfFaturamentoMensal}
                  onChange={(e) => setCpfFaturamentoMensal(e.target.value)}
                  placeholder="Ex: 5000"
                />
              </label>

              <label>
                <span>Despesas mensais</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={cpfDespesasMensais}
                  onChange={(e) => setCpfDespesasMensais(e.target.value)}
                  placeholder="Ex: 1000"
                />
              </label>
            </div>
          </section>
        )}

        <section className="impacto-hero">
          <article className="card card-impacto">
            <span className="card-label">
              {tipoPerfil === "mei"
                ? "DAS Estimado Anual"
                : tipoPerfil === "cpf"
                  ? "IRPF Estimado Anual"
                  : "Impacto Financeiro Anual"}
            </span>
            <strong className="card-valor-impacto">
              R$ {(impacto ?? 0).toLocaleString("pt-BR")}
            </strong>
            <p className="card-sub">
              {tipoPerfil === "mei"
                ? "Imposto mensal estimado × 12"
                : tipoPerfil === "cpf"
                  ? "Imposto de renda estimado no ano"
                  : "Valor recuperável estimado no ano"}
            </p>
          </article>
        </section>

        <section className="cards-grid">
          {cardsDashboard.map((card) => (
            <article
              className={`card ${card.id === "severidade-risco" ? `card-severidade-${severidadeRisco}` : ""}`}
              key={card.id}
              data-card-id={card.id}
            >
              <span className="card-label">{card.titulo}</span>
              <strong>{card.valor}</strong>
            </article>
          ))}
        </section>

        {!data?.consulta_paga && (
          <div className="bloqueio-relatorio">
            <span className="icone-bloqueio">🔒</span>
            <h3>Diagnóstico completo bloqueado</h3>
            <p>Realize o pagamento para acessar o relatório detalhado.</p>
            <button
              type="button"
              className="btn-desbloquear"
              onClick={iniciarCheckout}
              disabled={checkoutLoading}
            >
              {checkoutLoading ? "Redirecionando..." : "💳 Desbloquear diagnóstico completo"}
            </button>
            {checkoutErro && (
              <span className="relatorio-pdf-erro" style={{ marginTop: 8 }}>
                {checkoutErro}
              </span>
            )}
          </div>
        )}

        {data?.consulta_paga && (
          <div className="bloqueio-relatorio liberado">
            <h3>Diagnóstico completo disponível</h3>
            <p>Baixe o relatório detalhado em PDF.</p>
            <RelatorioPDFButton idPerfil={idPerfil} />
          </div>
        )}

        <section className="chart-card">
          <div className="section-header">
            <h3>Evolução da Recuperação</h3>
            <p>Últimos meses</p>
          </div>

          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={dadosEvolucao}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="mes" />
                <YAxis />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="recuperacao"
                  strokeWidth={3}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="chart-card">
          <div className="section-header">
            <h3>Distribuição por NCM</h3>
            <p>Impacto fiscal por categoria</p>
          </div>

          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={dadosNCM}
                  dataKey="valor"
                  nameKey="nome"
                  outerRadius={90}
                  label
                >
                  <Cell fill="#1e3a8a" />
                  <Cell fill="#2563eb" />
                  <Cell fill="#3b82f6" />
                  <Cell fill="#60a5fa" />
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </section>
      </main>
    </div>
  )
}

export default App

import React, { useState, useEffect } from "react"
import "./App.css"
import useDashboardData from "./hooks/useDashboardData"
import RelatorioPDFButton from "./components/RelatorioPDFButton"
import {
  API_BASE,
  getToken,
  isAuthenticated,
  isDemoSession,
  clearToken,
  login,
  loginDemo
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

  const perfisDisponiveis = [
    { tipo: "empresa", id: 4, nome: "Empresa" },
    { tipo: "cpf", id: 1, nome: "Pessoa Física" }
  ]
  const [perfilAtual, setPerfilAtual] = React.useState(perfisDisponiveis[0])

  const tipoPerfil = perfilAtual.tipo
  const idPerfil = perfilAtual.id

  const { data, historico, tendencia, loading, risco, pontuacao, impacto } = useDashboardData(tipoPerfil, idPerfil)
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
      if (email === "demo@demo.com") {
        loginDemo()
        window.location.reload()
        return
      }

      await login(email, password)
      window.location.reload()
    } catch (err) {
      setErroLogin("Credenciais inválidas")
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
        if (isDemoSession()) {
          setUsuario({
            id: 0,
            email: "demo@demo.com",
            plano_id: 3,
            consulta_paga: true
          })
          setVerificandoSessao(false)
          return
        }

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
              setPerfilAtual({
                tipo: "empresa",
                id: e.id,
                nome: e.razao_social || `Empresa #${e.id}`
              })
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

  async function enviarXML(file) {
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
      return
    }

    if (data.job_id) {
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
        }
      }, 2000)

      return
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
        <input
          type="file"
          accept=".xml"
          onChange={(e) => enviarXML(e.target.files[0])}
        />
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

        <section className="impacto-hero">
          <article className="card card-impacto">
            <span className="card-label">Impacto Financeiro Anual</span>
            <strong className="card-valor-impacto">
              R$ {(impacto ?? 0).toLocaleString("pt-BR")}
            </strong>
            <p className="card-sub">Valor recuperável estimado no ano</p>
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

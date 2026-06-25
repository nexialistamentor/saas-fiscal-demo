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
  logout,
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

// B2-DASH-02: NCM real virá de itens_fiscais via endpoint dedicado futuro.
// Sem mock: quando não há NCM real, a UI mostra estado indisponível.
const dadosNCM = []

const TIPOS_RENDIMENTO_OPTS = [
  { id: "salario", label: "Salário" },
  { id: "autonomo", label: "Autônomo" },
  { id: "aluguel", label: "Aluguel" },
  { id: "investimento", label: "Investimento" },
  { id: "outro", label: "Outro" }
]

function App() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [usuario, setUsuario] = useState(null)
  const [erroLogin, setErroLogin] = useState(null)

  const [mostrarSenhaLogin, setMostrarSenhaLogin] = useState(false)

  const [mostrarSenhaRegisto, setMostrarSenhaRegisto] = useState(false)
  const [verificandoSessao, setVerificandoSessao] = useState(true)
  const [precisaAceitarTermos, setPrecisaAceitarTermos] = useState(false)
  const [erroTermos, setErroTermos] = useState("")

  const [mostrarRegisto, setMostrarRegisto] = useState(false)
  const [nomeRegisto, setNomeRegisto] = useState("")
  const [emailRegisto, setEmailRegisto] = useState("")
  const [passwordRegisto, setPasswordRegisto] = useState("")
  const [tipoRegisto, setTipoRegisto] = useState("mei")
  const [documentoRegisto, setDocumentoRegisto] = useState("")
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
  const [meiFaturamentoMensal, setMeiFaturamentoMensal] = useState("")
  const [meiDespesasMensais, setMeiDespesasMensais] = useState("")

  const meiResult = useMeiDashboard({
    faturamento_mensal: meiFaturamentoMensal,
    despesas: meiDespesasMensais
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
    risco === -1 ? "indisponivel" :
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

  const [uploadRendimentoResposta, setUploadRendimentoResposta] = useState(null)
  const [formRendimento, setFormRendimento] = useState({
    tipo_rendimento: "salario",
    descricao: "",
    valor: "",
    ano_referencia: new Date().getFullYear(),
    mes_referencia: new Date().getMonth() + 1,
    fonte_pagadora: "",
  })
  const [rendimentoEnviando, setRendimentoEnviando] = useState(false)
  const [rendimentoConfirmado, setRendimentoConfirmado] = useState(null)
  const [rendimentoErro, setRendimentoErro] = useState(null)

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
          nome: nomeRegisto,
          tipo_usuario: tipoRegisto,
          documento: documentoRegisto || null
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

  async function handleAceitarTermos() {
    try {
      const res = await fetch(`${API_BASE}/auth/accept-terms`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}` }
      })
      if (res.status === 401) {
        clearToken()
        window.location.reload()
        return
      }
      if (res.ok) {
        setPrecisaAceitarTermos(false)
        window.location.reload()
      } else {
        alert("Erro ao aceitar os termos. Tente novamente.")
      }
    } catch (e) {
      console.error("[Termos] Erro ao aceitar:", e)
      alert("Erro de rede. Verifique a ligacao e tente novamente.")
    }
  }

  async function handleLogout() {
    await logout()
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

        if (!res.ok) {
          clearToken()
          setVerificandoSessao(false)
          return
        }

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

        // B10-TERMOS-01: verificar aceite de termos — falha controlada, nao silenciosa
        try {
          const termosRes = await fetch(`${API_BASE}/auth/has-accepted-terms`, {
            headers: { Authorization: `Bearer ${getToken()}` }
          })
          if (termosRes.status === 401) {
            clearToken()
            setVerificandoSessao(false)
            return
          }
          if (!termosRes.ok) {
            setErroTermos("Nao foi possivel verificar o aceite dos termos. Tente novamente.")
            setVerificandoSessao(false)
            return
          }
          const termosData = await termosRes.json()
          if (!termosData.accepted) {
            setPrecisaAceitarTermos(true)
            setVerificandoSessao(false)
            return
          }
        } catch (e) {
          console.warn("[Termos] Erro de rede:", e)
          setErroTermos("Erro de rede ao verificar os termos. Verifique a ligacao e tente novamente.")
          setVerificandoSessao(false)
          return
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
    if (tipoPerfil === "cpf") return
    if (!data?.consulta_paga) return
    if (!resultadoXML?.relatorio_id) return
    if (resultadoXML?.carregado) return

    carregarRelatorioSeguro(resultadoXML.relatorio_id)
  }, [tipoPerfil, data?.consulta_paga, resultadoXML?.relatorio_id, resultadoXML?.carregado])

  if (erroTermos) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg-primary, #0f1117)", padding: "2rem" }}>
        <div style={{ background: "var(--bg-card, #1a1d2e)", borderRadius: "12px", padding: "2.5rem", maxWidth: "420px", width: "100%", textAlign: "center", border: "1px solid #ef4444" }}>
          <h2 style={{ color: "#ef4444", marginBottom: "1rem" }}>Verificacao dos termos indisponivel</h2>
          <p style={{ color: "var(--text-secondary, #9ca3af)", marginBottom: "1.5rem", lineHeight: "1.6" }}>{erroTermos}</p>
          <button onClick={() => window.location.reload()} style={{ background: "var(--accent-color, #6366f1)", color: "#fff", border: "none", borderRadius: "8px", padding: "0.75rem 1.5rem", cursor: "pointer", marginRight: "0.75rem", fontWeight: "600" }}>
            Tentar novamente
          </button>
          <button onClick={handleLogout} style={{ background: "transparent", color: "var(--text-secondary, #9ca3af)", border: "1px solid var(--border-color, #2a2d3e)", borderRadius: "8px", padding: "0.75rem 1.5rem", cursor: "pointer" }}>
            Sair
          </button>
        </div>
      </div>
    )
  }

  if (precisaAceitarTermos) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg-primary, #0f1117)", padding: "2rem" }}>
        <div style={{ background: "var(--bg-card, #1a1d2e)", borderRadius: "12px", padding: "2.5rem", maxWidth: "480px", width: "100%", textAlign: "center", border: "1px solid var(--border-color, #2a2d3e)" }}>
          <h2 style={{ color: "var(--text-primary, #fff)", marginBottom: "1rem", fontSize: "1.4rem" }}>Termos de Uso</h2>
          <p style={{ color: "var(--text-secondary, #9ca3af)", marginBottom: "1.5rem", lineHeight: "1.6" }}>
            Para utilizar a plataforma Tributaria L2, e necessario aceitar os Termos de Uso e a Politica de Privacidade.
            Os seus dados fiscais serao tratados de forma soberana, auditavel e em conformidade com a LGPD.
          </p>
          <ul style={{ color: "var(--text-secondary, #9ca3af)", textAlign: "left", marginBottom: "1.5rem", paddingLeft: "1.2rem", lineHeight: "1.8" }}>
            <li>Os seus documentos sao tratados de forma confidencial</li>
            <li>Os calculos fiscais sao informativos — nao substituem parecer profissional</li>
            <li>Pode solicitar a eliminacao dos seus dados a qualquer momento</li>
            <li>O acesso a analises e pessoal e intransferivel</li>
          </ul>
          <button onClick={handleAceitarTermos} style={{ background: "var(--accent-color, #6366f1)", color: "#fff", border: "none", borderRadius: "8px", padding: "0.85rem 2rem", fontSize: "1rem", cursor: "pointer", width: "100%", fontWeight: "600" }}>
            Aceitar e continuar
          </button>
          <button onClick={handleLogout} style={{ background: "transparent", color: "var(--text-secondary, #9ca3af)", border: "none", marginTop: "0.75rem", cursor: "pointer", fontSize: "0.9rem", textDecoration: "underline" }}>
            Sair
          </button>
        </div>
      </div>
    )
  }

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

              <div style={{ position: "relative", display: "inline-block" }}>
                <input
                  type={mostrarSenhaLogin ? "text" : "password"}
                  placeholder="senha"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  onClick={() => setMostrarSenhaLogin(!mostrarSenhaLogin)}
                  style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", fontSize: 14 }}
                >
                  {mostrarSenhaLogin ? "🙈" : "👁️"}
                </button>
              </div>

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
              <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
                {["cpf", "mei", "empresa"].map((tipo) => (
                  <button
                    key={tipo}
                    type="button"
                    onClick={() => { setTipoRegisto(tipo); setDocumentoRegisto("") }}
                    style={{
                      padding: "6px 14px",
                      borderRadius: 4,
                      border: "1px solid #ccc",
                      background: tipoRegisto === tipo ? "#1e3a8a" : "#fff",
                      color: tipoRegisto === tipo ? "#fff" : "#333",
                      cursor: "pointer",
                      fontWeight: tipoRegisto === tipo ? "bold" : "normal"
                    }}
                  >
                    {tipo.toUpperCase()}
                  </button>
                ))}
              </div>

              {tipoRegisto !== "cpf" && (
                <input
                  type="text"
                  placeholder="Nome da empresa"
                  value={nomeRegisto}
                  onChange={(e) => setNomeRegisto(e.target.value)}
                />
              )}

              <input
                type="text"
                placeholder={tipoRegisto === "cpf" ? "CPF (somente números)" : "CNPJ (somente números)"}
                value={documentoRegisto}
                onChange={(e) => setDocumentoRegisto(e.target.value)}
              />

              <input
                type="email"
                placeholder="email"
                value={emailRegisto}
                onChange={(e) => setEmailRegisto(e.target.value)}
              />

              <div style={{ position: "relative", display: "inline-block" }}>
                <input
                  type={mostrarSenhaRegisto ? "text" : "password"}
                  placeholder="senha"
                  value={passwordRegisto}
                  onChange={(e) => setPasswordRegisto(e.target.value)}
                  aria-describedby="hint-password-registo"
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  onClick={() => setMostrarSenhaRegisto(!mostrarSenhaRegisto)}
                  style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", fontSize: 14 }}
                >
                  {mostrarSenhaRegisto ? "🙈" : "👁️"}
                </button>
              </div>
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
      valor: risco === -1 ? "N/D" : `${risco}%`,
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
      valor: pontuacao === -1 ? "N/D" : `${pontuacao}/100`,
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

  async function enviarDocumentoRendimento(file) {
    if (!file) return
    setRendimentoErro(null)
    setRendimentoConfirmado(null)
    const formData = new FormData()
    formData.append("file", file)
    const resp = await fetch(`${API_BASE}/cpf/documentos/upload`, {
      method: "POST",
      headers: { Authorization: `Bearer ${getToken()}` },
      body: formData
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      setRendimentoErro(
        typeof err.detail === "string" ? err.detail : "Falha no envio do ficheiro."
      )
      return
    }
    const json = await resp.json()
    setUploadRendimentoResposta({
      arquivo_nome: json.arquivo_nome,
      tamanho: json.tamanho
    })
  }

  async function confirmarRendimento(e) {
    e.preventDefault()
    setRendimentoEnviando(true)
    setRendimentoErro(null)
    try {
      const rawValor = String(formRendimento.valor).trim()
      const valorNum =
        rawValor === "" ? null : Number(rawValor.replace(",", "."))
      const res = await fetch(`${API_BASE}/cpf/documentos/confirmar`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${getToken()}`,
        },
        body: JSON.stringify({
          tipo_rendimento: formRendimento.tipo_rendimento,
          descricao: formRendimento.descricao || null,
          valor: valorNum,
          ano_referencia:
            formRendimento.ano_referencia === "" || formRendimento.ano_referencia == null
              ? null
              : Number(formRendimento.ano_referencia),
          mes_referencia:
            formRendimento.mes_referencia === "" || formRendimento.mes_referencia == null
              ? null
              : Number(formRendimento.mes_referencia),
          fonte_pagadora: formRendimento.fonte_pagadora || null,
          confianca_extracao: "manual"
        })
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(
          typeof err.detail === "string" ? err.detail : "Não foi possível guardar o rendimento."
        )
      }
      const j = await res.json()
      setRendimentoConfirmado(j)
      setUploadRendimentoResposta(null)
      setFormRendimento((f) => ({
        ...f,
        descricao: "",
        valor: ""
      }))
    } catch (err) {
      setRendimentoErro(err.message)
    } finally {
      setRendimentoEnviando(false)
    }
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

      {tipoPerfil === "cpf" && podeUploadXML && (
        <div
          className="card"
          style={{ margin: "20px 24px 0", maxWidth: 520, padding: 20, border: "1px solid #e2e8f0" }}
        >
          <h3 style={{ marginTop: 0 }}>Documentos de rendimento</h3>
          <p style={{ fontSize: 14, color: "#475569" }}>
            Envie um comprovativo (PDF ou imagem). Depois confirme o tipo e os valores para
            registo, conforme o passo de confirmação da API.
          </p>
          <input
            type="file"
            accept=".pdf,image/*,application/pdf"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) enviarDocumentoRendimento(f)
              e.target.value = ""
            }}
          />
          {uploadRendimentoResposta && (
            <p style={{ fontSize: 13, marginTop: 8 }}>
              Ficheiro recebido: <strong>{uploadRendimentoResposta.arquivo_nome}</strong> (
              {uploadRendimentoResposta.tamanho} bytes)
            </p>
          )}
          {rendimentoConfirmado && (
            <p style={{ marginTop: 12, color: "#166534" }}>
              Rendimento guardado (id {rendimentoConfirmado.id}).
            </p>
          )}
          <form onSubmit={confirmarRendimento} style={{ marginTop: 16, display: "grid", gap: 10 }}>
            <label>
              Tipo de rendimento
              <select
                value={formRendimento.tipo_rendimento}
                onChange={(e) =>
                  setFormRendimento((f) => ({ ...f, tipo_rendimento: e.target.value }))
                }
              >
                {TIPOS_RENDIMENTO_OPTS.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Descrição (opcional)
              <input
                type="text"
                value={formRendimento.descricao}
                onChange={(e) =>
                  setFormRendimento((f) => ({ ...f, descricao: e.target.value }))
                }
              />
            </label>
            <label>
              Valor (R$)
              <input
                type="text"
                inputMode="decimal"
                value={formRendimento.valor}
                onChange={(e) =>
                  setFormRendimento((f) => ({ ...f, valor: e.target.value }))
                }
                placeholder="Ex: 1500,50"
              />
            </label>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <label>
                Mês
                <input
                  type="number"
                  min={1}
                  max={12}
                  value={formRendimento.mes_referencia}
                  onChange={(e) =>
                    setFormRendimento((f) => ({
                      ...f,
                      mes_referencia: e.target.value === "" ? "" : Number(e.target.value)
                    }))
                  }
                />
              </label>
              <label>
                Ano
                <input
                  type="number"
                  min={2000}
                  max={2100}
                  value={formRendimento.ano_referencia}
                  onChange={(e) =>
                    setFormRendimento((f) => ({
                      ...f,
                      ano_referencia: e.target.value === "" ? "" : Number(e.target.value)
                    }))
                  }
                />
              </label>
            </div>
            <label>
              Fonte pagadora (opcional)
              <input
                type="text"
                value={formRendimento.fonte_pagadora}
                onChange={(e) =>
                  setFormRendimento((f) => ({ ...f, fonte_pagadora: e.target.value }))
                }
              />
            </label>
            <button type="submit" disabled={rendimentoEnviando}>
              {rendimentoEnviando ? "A guardar…" : "Confirmar e guardar rendimento"}
            </button>
          </form>
          {rendimentoErro && (
            <p style={{ color: "#b91c1c", marginTop: 8 }}>{rendimentoErro}</p>
          )}
        </div>
      )}

      {tipoPerfil === "cpf" && !podeUploadXML && (
        <div style={{ marginTop: 20, marginLeft: 24, marginRight: 24 }}>
          <p>Envio de documentos de rendimento disponível apenas em planos superiores.</p>
        </div>
      )}

      {tipoPerfil !== "cpf" && podeUploadXML && (
        <input
          type="file"
          accept=".xml"
          multiple
          onChange={(e) => enviarXML(Array.from(e.target.files ?? []))}
        />
      )}

      {tipoPerfil !== "cpf" && !podeUploadXML && (
        <div style={{ marginTop: 20 }}>
          <p>Upload de XML disponível apenas em planos superiores.</p>
        </div>
      )}

      {tipoPerfil !== "cpf" && resultadoXML && !data?.consulta_paga && (
        <div style={{ marginTop: 20, padding: 20, border: "1px solid #ccc", borderRadius: 8 }}>
          <h3>Análise concluída</h3>
          <p>Seu XML foi processado com sucesso.</p>
          <p>Foram identificados elementos fiscais que podem compor um diagnóstico técnico.</p>
          <p>Desbloqueie o relatório completo para visualizar detalhes, fundamentos e valores recuperáveis.</p>
        </div>
      )}

      {tipoPerfil !== "cpf" && resultadoXML?.carregado && data?.consulta_paga && (() => {
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

        {perfilAtual.tipo === "mei" && (
          <section className="card" style={{ marginBottom: 20 }}>
            <h3>Dados para simulação MEI</h3>

            <div style={{ display: "grid", gap: 12, maxWidth: 420 }}>
              <label>
                <span>Faturamento mensal</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={meiFaturamentoMensal}
                  onChange={(e) => setMeiFaturamentoMensal(e.target.value)}
                  placeholder="Ex: 5000"
                />
              </label>

              <label>
                <span>Despesas mensais</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={meiDespesasMensais}
                  onChange={(e) => setMeiDespesasMensais(e.target.value)}
                  placeholder="Ex: 1000"
                />
              </label>
            </div>
          </section>
        )}

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
            <MemorialButton relatorioId={resultadoXML?.relatorio_id} />
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
              {dadosNCM.length === 0 ? (
                <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", textAlign: "center", padding: "1rem 0" }}>
                  Dados de NCM indisponíveis para este relatório.
                </p>
              ) : (
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
              )}
            </ResponsiveContainer>
          </div>
        </section>
      </main>
    </div>
  )
}

function MemorialButton({ relatorioId }) {
  const [loading, setLoading] = React.useState(false)
  const [erro, setErro] = React.useState(null)

  if (!relatorioId) return null

  async function baixarMemorial() {
    setLoading(true)
    setErro(null)
    try {
      const res = await fetch(`${API_BASE}/relatorio/memorial/${relatorioId}/pdf`, {
        method: "GET",
        headers: { Authorization: `Bearer ${getToken()}` }
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || "Erro ao gerar memorial.")
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `memorial-${relatorioId}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setErro(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ marginTop: 8 }}>
      <button
        type="button"
        className="btn-desbloquear"
        onClick={baixarMemorial}
        disabled={loading}
      >
        {loading ? "A gerar..." : "📄 Baixar Memorial de Cálculo"}
      </button>
      {erro && <span className="relatorio-pdf-erro" style={{ marginTop: 4 }}>{erro}</span>}
    </div>
  )
}

export default App

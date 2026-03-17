import React, { useState } from "react"
import "./App.css"
import useDashboardData from "./hooks/useDashboardData"
import RelatorioPDFButton from "./components/RelatorioPDFButton"
import { API_BASE, getToken } from "./config"
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
  const perfisDisponiveis = [
    { tipo: "empresa", id: 4, nome: "Perfil" },
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

  if (loading) {
    return <p style={{ padding: 40 }}>Carregando dados fiscais...</p>
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

  return (
    <div className="app">
      <header className="topbar">
        <div className="hero">
          <h1>Plataforma de Inteligência Tributária em Tempo Real</h1>
        </div>

        <button className="menu-btn">☰</button>
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

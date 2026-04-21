import { useCallback, useEffect, useState } from "react"
import { API_BASE, clearToken, getToken, isAuthenticated } from "../config"

export default function useDashboardData(tipoPerfil = "empresa", idPerfil = 5, cpfContexto = {}) {
  const [data, setData] = useState(null)
  const [historico, setHistorico] = useState([])
  const [tendencia, setTendencia] = useState(null)
  const [loading, setLoading] = useState(true)

  const cpfFaturamentoMensal = Number(cpfContexto.faturamento_mensal || 0)
  const cpfDespesasMensais = Number(cpfContexto.despesas || 0)

  const carregar = useCallback(async () => {
    console.log("HOOK DASHBOARD EXECUTANDO", { tipoPerfil, idPerfil })
    if (tipoPerfil === "cpf") {
      if (!isAuthenticated()) {
        setLoading(false)
        return
      }

      try {
        const TOKEN = getToken()
        if (!TOKEN) {
          setLoading(false)
          return
        }

        const headers = {
          "Content-Type": "application/json",
          Authorization: `Bearer ${TOKEN}`
        }

        const body = JSON.stringify({
          faturamento_mensal: cpfFaturamentoMensal,
          despesas: cpfDespesasMensais
        })

        const res = await fetch(`${API_BASE}/cpf/dashboard`, {
          method: "POST",
          headers,
          body
        })

        const json = await res.json()

        setData({
          impacto_financeiro_anual: json.imposto_anual ?? 0,
          pontuacao_fiscal: 70,
          risco_tributario_percentual: 30,
          total_insights: json.alertas?.length || 0,
          consulta_paga: true
        })
        setHistorico([])
        setTendencia({ tendencia: "insuficiente" })
      } catch (erro) {
        console.error("[Dashboard CPF] erro:", erro)
      } finally {
        setLoading(false)
      }
      return
    }
    if (!idPerfil) {
      setLoading(false)
      return
    }
    if (!isAuthenticated()) {
      setLoading(false)
      return
    }
    try {
      const TOKEN = getToken()
      if (!TOKEN) {
        setLoading(false)
        return
      }
      const headers = {
        Authorization: `Bearer ${TOKEN}`
      }
      const baseURL = `${API_BASE}/inteligencia`
      const urlMapa = `${baseURL}/mapa-oportunidades/${idPerfil}`
      console.log("CHAMANDO API DASHBOARD", {
        urlMapa,
        urlHistorico: `${baseURL}/historico-inteligencia/${idPerfil}`,
        urlTendencia: `${baseURL}/tendencia-inteligencia/${idPerfil}`,
        token: TOKEN ? "presente" : "ausente"
      })
      const [resMapa, resHistorico, resTendencia] = await Promise.all([
        fetch(urlMapa, { headers }),
        fetch(`${baseURL}/historico-inteligencia/${idPerfil}`, { headers }),
        fetch(`${baseURL}/tendencia-inteligencia/${idPerfil}`, { headers })
      ])
      if (resMapa.status === 401) {
        clearToken()
        window.location.reload()
        return
      }
      if (!resMapa.ok) {
        const errBody = await resMapa.text()
        console.error(
          `[Dashboard] mapa-oportunidades falhou: status=${resMapa.status} url=${urlMapa}`,
          errBody
        )
        return
      }
      const mapaJson = await resMapa.json()
      const historicoJson = await resHistorico.json()
      const tendenciaJson = resTendencia.ok ? await resTendencia.json() : null
      const mapaSeguro =
        mapaJson != null && typeof mapaJson === "object" && !Array.isArray(mapaJson)
          ? mapaJson
          : null
      if (mapaSeguro == null) {
        console.warn(
          "[Dashboard] mapa-oportunidades formato inesperado (debug):",
          JSON.stringify(mapaJson)
        )
      }
      setData(mapaSeguro ?? {})
      setHistorico(Array.isArray(historicoJson) ? historicoJson : [])
      setTendencia(tendenciaJson ?? { tendencia: "insuficiente" })
    } catch (erro) {
      console.error("[Dashboard] Erro ao carregar (CORS/rede?):", erro)
    } finally {
      setLoading(false)
    }
  }, [idPerfil, tipoPerfil, cpfFaturamentoMensal, cpfDespesasMensais])

  useEffect(() => {
    carregar()
    const intervalo = setInterval(carregar, 60000)
    return () => clearInterval(intervalo)
  }, [carregar])

  // Valores derivados dos campos da API (escalas 0-100, impactos corretos)
  const risco = data ? Math.min(100, data.risco_tributario_percentual ?? 0) : 0
  const pontuacao = data
    ? Math.min(100, Math.max(0, data.pontuacao_fiscal ?? 0))
    : 0
  const impacto =
    data?.impacto_financeiro_anual ??
    (data?.restituicao_st ?? 0) * 12

  return {
    data,
    historico,
    tendencia,
    loading,
    risco,
    pontuacao,
    impacto,
    refetch: carregar,
  }
}

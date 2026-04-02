import { useCallback, useEffect, useState } from "react"
import { API_BASE, clearToken, getToken, isAuthenticated, isDemoSession } from "../config"

export default function useDashboardData(tipoPerfil = "empresa", idPerfil = 5, enabled = false) {
  const [data, setData] = useState(null)
  const [historico, setHistorico] = useState([])
  const [tendencia, setTendencia] = useState(null)
  const [loading, setLoading] = useState(true)

  const aplicarMapaOportunidades = useCallback((mapaJson) => {
    const mapaSeguro =
      mapaJson != null && typeof mapaJson === "object" && !Array.isArray(mapaJson)
        ? mapaJson
        : null
    if (mapaSeguro == null && mapaJson != null) {
      console.warn(
        "[Dashboard] mapa-oportunidades formato inesperado (pós-lote):",
        JSON.stringify(mapaJson)
      )
    }
    setData(mapaSeguro ?? {})
  }, [])

  useEffect(() => {
    const token = getToken()
    const sessionDemo = isDemoSession(token)

    if (sessionDemo) {
      setData({
        restituicao_st: 280000,
        risco_tributario_percentual: 12,
        pontuacao_fiscal: 96,
        impacto_financeiro_anual: 1680000,
        estoque_fantasma: 0,
        total_insights: 48,
        consulta_paga: true,
        context_flags: {
          dados_incompletos: true,
          valores_normalizados: true,
          usa_estimativa: true,
          base_presumida: false
        },
        decomposicao_impacto: {
          valor_recuperavel_real: 1350000,
          valor_estimado: 330000,
          normalizacoes_aplicadas: 2
        }
      })
      setHistorico([
        { data_snapshot: "2025-11-01", score_global: 78, risco_tributario: 38, maturidade_tributaria: 72 },
        { data_snapshot: "2025-12-01", score_global: 84, risco_tributario: 30, maturidade_tributaria: 79 },
        { data_snapshot: "2026-01-01", score_global: 90, risco_tributario: 22, maturidade_tributaria: 87 },
        { data_snapshot: "2026-02-01", score_global: 96, risco_tributario: 12, maturidade_tributaria: 93 }
      ])
      setTendencia({ tendencia: "melhoria_forte" })
      setLoading(false)
      return
    }

    async function carregar() {
      if (!enabled) {
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

        aplicarMapaOportunidades(mapaJson)

        setHistorico(Array.isArray(historicoJson) ? historicoJson : [])
        setTendencia(tendenciaJson ?? { tendencia: "insuficiente" })

      } catch (erro) {

        console.error("[Dashboard] Erro ao carregar (CORS/rede?):", erro)

      } finally {

        setLoading(false)

      }
    }

    carregar()

    const intervalo = setInterval(carregar, 15000)

    return () => clearInterval(intervalo)

  }, [idPerfil, tipoPerfil, enabled, aplicarMapaOportunidades])

  // Valores derivados dos campos da API (escalas 0-100, impactos corretos)
  const risco = data ? Math.min(100, data.risco_tributario_percentual ?? 0) : 0
  const pontuacao = data
    ? Math.min(100, Math.max(0, data.pontuacao_fiscal ?? 0))
    : 0
  const impacto =
    data?.impacto_financeiro_anual ?? 0

  const decomposicaoImpacto = data?.decomposicao_impacto ?? null
  const contextFlags = data?.context_flags ?? null

  return {
    data,
    historico,
    tendencia,
    loading,
    risco,
    pontuacao,
    impacto,
    decomposicaoImpacto,
    contextFlags,
    aplicarMapaOportunidades
  }
}

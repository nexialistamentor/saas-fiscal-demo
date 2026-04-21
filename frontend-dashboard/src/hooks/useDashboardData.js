import { useCallback, useEffect, useState } from "react"
import { API_BASE, clearToken, getToken, isAuthenticated } from "../config"

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

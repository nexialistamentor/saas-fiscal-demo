import { useCallback, useEffect, useState } from "react"
import { API_BASE, clearToken, getToken, isAuthenticated } from "../config"
export default function useEmpresaDashboard(idPerfil) {
  const [data, setData] = useState(null)
  const [historico, setHistorico] = useState([])
  const [tendencia, setTendencia] = useState(null)
  const [loading, setLoading] = useState(true)
  const carregar = useCallback(async () => {
    if (!idPerfil) { setLoading(false); return }
    if (!isAuthenticated()) { setLoading(false); return }
    const TOKEN = getToken()
    if (!TOKEN) { setLoading(false); return }
    try {
      const headers = { Authorization: `Bearer ${TOKEN}` }
      const baseURL = `${API_BASE}/inteligencia`
      const [resMapa, resHistorico, resTendencia] = await Promise.all([
        fetch(`${baseURL}/mapa-oportunidades/${idPerfil}`, { headers }),
        fetch(`${baseURL}/historico-inteligencia/${idPerfil}`, { headers }),
        fetch(`${baseURL}/tendencia-inteligencia/${idPerfil}`, { headers })
      ])
      if (resMapa.status === 401) {
        clearToken()
        window.location.reload()
        return
      }
      if (!resMapa.ok) {
        console.error(`[Dashboard Empresa] mapa falhou: ${resMapa.status}`)
        return
      }
      const mapaJson = await resMapa.json()
      const historicoJson = resHistorico.ok ? await resHistorico.json() : []
      const tendenciaJson = resTendencia.ok ? await resTendencia.json() : null
      const mapaSeguro =
        mapaJson != null && typeof mapaJson === "object" && !Array.isArray(mapaJson)
          ? mapaJson : null
      setData(mapaSeguro ?? {})
      setHistorico(Array.isArray(historicoJson) ? historicoJson : [])
      setTendencia(tendenciaJson ?? { tendencia: "insuficiente" })
    } catch (erro) {
      console.error("[Dashboard Empresa] erro:", erro)
    } finally {
      setLoading(false)
    }
  }, [idPerfil])
  useEffect(() => {
    carregar()
    const intervalo = setInterval(carregar, 60000)
    return () => clearInterval(intervalo)
  }, [carregar])
  const risco = data ? Math.min(100, data.risco_tributario_percentual ?? 0) : 0
  const pontuacao = data ? Math.min(100, Math.max(0, data.pontuacao_fiscal ?? 0)) : 0
  const impacto = data?.impacto_financeiro_anual ?? (data?.restituicao_st ?? 0) * 12
  return {
    data,
    historico,
    tendencia,
    loading,
    risco,
    pontuacao,
    impacto,
    refetch: carregar
  }
}

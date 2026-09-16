import { useCallback, useEffect, useState } from "react"
import { API_BASE, fetchAutenticado, isAuthenticated } from "../config"
export default function useEmpresaDashboard(idPerfil) {
  const [data, setData] = useState(null)
  const [historico, setHistorico] = useState(null)
  const [tendencia, setTendencia] = useState(null)
  const [loading, setLoading] = useState(true)
  const carregar = useCallback(async () => {
    if (!idPerfil) { setLoading(false); return }
    if (!isAuthenticated()) { setLoading(false); return }
    try {
      const baseURL = `${API_BASE}/inteligencia`
      const [resMapa, resHistorico, resTendencia] = await Promise.all([
        fetchAutenticado(`${baseURL}/mapa-oportunidades/${idPerfil}`),
        fetchAutenticado(`${baseURL}/historico-inteligencia/${idPerfil}`),
        fetchAutenticado(`${baseURL}/tendencia-inteligencia/${idPerfil}`)
      ])
      const historicoJson = resHistorico?.ok ? await resHistorico.json() : null
      setHistorico(Array.isArray(historicoJson) ? historicoJson : null)
      if (!resMapa) {
        setData(null)
        setLoading(false)
        return
      }
      if (!resMapa.ok) {
        setData(null)
        console.error("[Dashboard Empresa] mapa falhou: " + resMapa.status)
        return
      }
      const mapaJson = await resMapa.json()
      const tendenciaJson = resTendencia?.ok ? await resTendencia.json() : null
      const mapaSeguro =
        mapaJson != null && typeof mapaJson === "object" && !Array.isArray(mapaJson)
          ? mapaJson : null
      setData(mapaSeguro)
      setTendencia(tendenciaJson ?? { tendencia: "insuficiente" })
    } catch (erro) {
      console.error("[Dashboard Empresa] erro:", erro)
      setData(null)
      setHistorico(null)
    } finally {
      setLoading(false)
    }
  }, [idPerfil])
  useEffect(() => {
    carregar()
    const intervalo = setInterval(carregar, 60000)
    return () => clearInterval(intervalo)
  }, [carregar])
  const risco = !data || data.context_flags?.dados_incompletos === true || data.risco_tributario_percentual == null
    ? -1
    : Math.min(100, data.risco_tributario_percentual)
  const pontuacao = data ? Math.min(100, Math.max(0, data.pontuacao_fiscal ?? 0)) : 0
  const impacto = data?.impacto_financeiro_anual != null
    ? data.impacto_financeiro_anual
    : data?.restituicao_st != null
      ? data.restituicao_st * 12
      : null
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

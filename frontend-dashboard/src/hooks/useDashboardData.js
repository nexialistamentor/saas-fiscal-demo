import { useEffect, useState } from "react"
import { API_BASE, getToken } from "../config"

export default function useDashboardData(tipoPerfil = "empresa", idPerfil = 5) {
  const [data, setData] = useState(null)
  const [historico, setHistorico] = useState([])
  const [tendencia, setTendencia] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    console.log("HOOK DASHBOARD EXECUTANDO", { tipoPerfil, idPerfil })

    async function carregar() {
      try {
        const TOKEN = getToken()
        console.log("TOKEN LOCAL:", localStorage.getItem("auth_token"))
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

        setData(mapaJson)
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

  }, [idPerfil, tipoPerfil])

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
  }
}

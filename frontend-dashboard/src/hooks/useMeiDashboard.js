import { useCallback, useEffect, useState } from "react"

import { API_BASE, fetchAutenticado, isAuthenticated } from "../config"

export default function useMeiDashboard(contexto = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const faturamentoMensal = Number(contexto.faturamento_mensal || 0)
  const despesasMensais = Number(contexto.despesas || 0)

  const carregar = useCallback(async () => {
    if (!isAuthenticated()) { setLoading(false); return }
    try {
      const res = await fetchAutenticado(`${API_BASE}/imposto/calcular`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tipo_usuario: "MEI",
          faturamento_mensal: faturamentoMensal,
          despesas: despesasMensais
        })
      })
      if (!res || !res.ok) {
        console.error("[Dashboard MEI] falhou:", res?.status)
        setLoading(false)
        return
      }
      const json = await res.json()
      setData({
        impacto_financeiro_anual: json.imposto_anual ?? 0,
        risco_tributario_percentual: null,
        pontuacao_fiscal: null,
        dados_indisponiveis: true,
        mensagem_indisponivel: "Análise de risco e pontuação ainda não disponível para MEI.",
        total_insights: json.alertas?.length || 0,
        consulta_paga: false,
        mei_imposto_mensal: json.imposto_mensal ?? 0,
        mei_alertas: json.alertas ?? []
      })
    } catch (erro) {
      console.error("[Dashboard MEI] erro:", erro)
    } finally {
      setLoading(false)
    }
  }, [faturamentoMensal, despesasMensais])

  useEffect(() => {
    carregar()
  }, [carregar])

  // -1 sentinela de indisponivel — App.jsx detecta e mostra "N/D"
  const risco = data
    ? (data.risco_tributario_percentual === null || data.risco_tributario_percentual === undefined
        ? -1 : Math.min(100, data.risco_tributario_percentual))
    : -1
  const pontuacao = data
    ? (data.pontuacao_fiscal === null || data.pontuacao_fiscal === undefined
        ? -1 : Math.min(100, Math.max(0, data.pontuacao_fiscal)))
    : -1
  const impacto = data?.impacto_financeiro_anual ?? 0

  return {
    data,
    historico: [],
    tendencia: { tendencia: "insuficiente" },
    loading,
    risco,
    pontuacao,
    impacto,
    refetch: carregar
  }
}

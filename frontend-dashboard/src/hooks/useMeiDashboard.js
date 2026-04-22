import { useCallback, useEffect, useState } from "react"

import { API_BASE, getToken, isAuthenticated } from "../config"

export default function useMeiDashboard(contexto = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const faturamentoMensal = Number(contexto.faturamento_mensal || 0)
  const despesasMensais = Number(contexto.despesas || 0)

  const carregar = useCallback(async () => {
    if (!isAuthenticated()) { setLoading(false); return }
    const TOKEN = getToken()
    if (!TOKEN) { setLoading(false); return }
    try {
      const res = await fetch(`${API_BASE}/imposto/calcular`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${TOKEN}`
        },
        body: JSON.stringify({
          tipo_usuario: "MEI",
          faturamento_mensal: faturamentoMensal,
          despesas: despesasMensais
        })
      })
      if (!res.ok) {
        console.error("[Dashboard MEI] falhou:", res.status)
        setLoading(false)
        return
      }
      const json = await res.json()
      setData({
        impacto_financeiro_anual: json.imposto_anual ?? 0,
        risco_tributario_percentual: 0,
        pontuacao_fiscal: 0,
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

  const risco = data ? Math.min(100, data.risco_tributario_percentual ?? 0) : 0
  const pontuacao = data ? Math.min(100, Math.max(0, data.pontuacao_fiscal ?? 0)) : 0
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

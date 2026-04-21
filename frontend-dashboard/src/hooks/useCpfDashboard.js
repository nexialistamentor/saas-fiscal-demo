import { useCallback, useEffect, useState } from "react"

import { API_BASE, getToken, isAuthenticated } from "../config"

export default function useCpfDashboard(contexto = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const faturamentoMensal = Number(contexto.faturamento_mensal || 0)
  const despesasMensais = Number(contexto.despesas || 0)

  const carregar = useCallback(async () => {
    if (!isAuthenticated()) { setLoading(false); return }
    const TOKEN = getToken()
    if (!TOKEN) { setLoading(false); return }
    try {
      const res = await fetch(`${API_BASE}/cpf/dashboard`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${TOKEN}`
        },
        body: JSON.stringify({
          faturamento_mensal: faturamentoMensal,
          despesas: despesasMensais
        })
      })
      if (!res.ok) {
        console.error("[Dashboard CPF] falhou:", res.status)
        setLoading(false)
        return
      }
      const json = await res.json()
      setData({
        impacto_financeiro_anual: json.imposto_anual ?? 0,
        risco_tributario_percentual: 30,
        pontuacao_fiscal: 70,
        total_insights: json.alertas?.length || 0,
        consulta_paga: true,
        cpf_imposto_mensal: json.imposto_mensal ?? 0,
        cpf_alertas: json.alertas ?? []
      })
    } catch (erro) {
      console.error("[Dashboard CPF] erro:", erro)
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

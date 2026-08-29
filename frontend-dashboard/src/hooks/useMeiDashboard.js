import { useCallback, useEffect, useState } from "react"

import { API_BASE, fetchAutenticado, isAuthenticated } from "../config"

export default function useMeiDashboard(contexto = {}) {
  const [data] = useState(null)
  const [loading, setLoading] = useState(true)

  const carregar = useCallback(async () => {
    if (!isAuthenticated()) { setLoading(false); return }
    setLoading(false)
  }, [])

  const emitirDasOficial = useCallback(async (empresaId, periodoApuracao, formato) => {
    if (!Number.isInteger(empresaId) || empresaId <= 0) {
      throw new TypeError("empresaId deve ser um inteiro positivo")
    }
    if (!["pdf", "codigo_barras"].includes(formato)) {
      throw new TypeError("formato deve ser pdf ou codigo_barras")
    }

    const res = await fetchAutenticado(`${API_BASE}/imposto/mei/${empresaId}/das`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        periodo_apuracao: periodoApuracao,
        formato: formato
      })
    })
    if (!res || !res.ok) {
      throw new Error(`Falha ao emitir DAS oficial: ${res?.status ?? "sem resposta"}`)
    }

    const resposta = await res.json()
    if (
      !resposta
      || typeof resposta !== "object"
      || !["emitido", "nao_emitido"].includes(resposta.estado_oficial)
    ) {
      throw new Error("Resposta oficial do DAS fora do contrato normalizado")
    }
    return resposta
  }, [])

  useEffect(() => {
    carregar()
  }, [carregar])

  // -1 sentinela de indisponivel - App.jsx detecta e mostra "N/D"
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
    emitirDasOficial,
    refetch: carregar
  }
}

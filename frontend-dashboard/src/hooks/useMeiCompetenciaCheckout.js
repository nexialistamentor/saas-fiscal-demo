import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { API_BASE, fetchAutenticado } from "../config"
import { criarMeiCompetenciaCheckout } from "../services/meiCompetenciaCheckout"

export default function useMeiCompetenciaCheckout({ empresaId, competencia, enabled }) {
  const client = useMemo(() => criarMeiCompetenciaCheckout({
    baseUrl: API_BASE,
    fetchAutenticado,
    storage: {
      getItem: key => localStorage.getItem(key),
      setItem: (key, value) => localStorage.setItem(key, value),
    },
    randomUUID: () => crypto.randomUUID(),
  }), [])
  const [snapshot, setSnapshot] = useState(null)
  const sequence = useRef(0)
  const busy = useRef(false)
  const scope = `${empresaId}:${competencia}`

  const atualizar = useCallback(async () => {
    const ticket = ++sequence.current
    if (!enabled || !/^\d{4}(0[1-9]|1[0-2])$/.test(competencia)) return
    setSnapshot({ scope, loading: true, compra: null, oferta: null, erro: "" })
    try {
      const compra = await client.recuperar({ empresaId, competencia })
      let oferta = null
      // A paid purchase remains recoverable even if the catalog is later held.
      if (compra?.estado !== "paid" && !compra?.checkout_url) oferta = await client.obterOferta()
      if (ticket === sequence.current) {
        setSnapshot({ scope, loading: false, compra, oferta, erro: "" })
      }
    } catch {
      if (ticket === sequence.current) {
        setSnapshot({ scope, loading: false, compra: null, oferta: null,
          erro: "Não foi possível verificar a compra. Atualize a confirmação antes de continuar." })
      }
    }
  }, [client, competencia, enabled, empresaId, scope])

  const invalidar = useCallback(() => { sequence.current += 1 }, [])

  useEffect(() => {
    atualizar()
    return invalidar
  }, [atualizar, invalidar])

  const state = enabled && snapshot?.scope === scope ? snapshot : null
  const iniciar = useCallback(async () => {
    if (busy.current || !enabled || !state || state.loading || state.erro) return null
    busy.current = true
    const ticket = ++sequence.current
    setSnapshot({ ...state, loading: true })
    try {
      const compra = await client.iniciar({ empresaId, competencia, oferta: state.oferta })
      if (ticket !== sequence.current) return null
      setSnapshot({ ...state, loading: false, compra, erro: "" })
      return compra
    } catch {
      if (ticket === sequence.current) {
        setSnapshot({ ...state, loading: false,
          erro: "Não foi possível abrir o checkout. Atualize para recuperar a tentativa antes de pagar." })
      }
      return null
    } finally { busy.current = false }
  }, [client, competencia, enabled, empresaId, state])

  return {
    compra: state?.compra ?? null,
    oferta: state?.oferta ?? null,
    loading: state?.loading ?? Boolean(enabled && competencia),
    erro: state?.erro ?? "",
    autorizado: state?.compra?.estado === "paid" && state.compra.autorizado === true,
    atualizar,
    iniciar,
  }
}

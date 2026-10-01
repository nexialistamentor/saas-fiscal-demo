// Purchase recovery is server-authoritative. Browser storage only retains retry keys.
const OFFER_CODE = "mei-das-one-time-company"

function validarEscopo({ empresaId, competencia }) {
  if (!Number.isInteger(empresaId) || empresaId <= 0
      || typeof competencia !== "string" || !/^\d{4}(0[1-9]|1[0-2])$/.test(competencia)) {
    throw new Error("Selecione uma empresa MEI e uma competência válida.")
  }
}

function chaveValida(value) {
  return typeof value === "string" && /^[\x21-\x7e]{1,255}$/.test(value)
}

function urlSegura(value) {
  if (typeof value !== "string" || /\s/.test(value)) return false
  try {
    const url = new URL(value)
    return url.protocol === "https:" && !!url.hostname && !url.username && !url.password && !url.hash
  } catch { return false }
}

function validarOferta(oferta) {
  if (!oferta || oferta.offer_code !== OFFER_CODE || oferta.vertical !== "tax"
      || oferta.commercial_model !== "one_time" || oferta.subject_type !== "company"
      || oferta.moeda !== "BRL" || oferta.preco !== "39.90"
      || oferta.billing_period !== null || oferta.usage_unit !== "competence"
      || oferta.usage_limit !== 1 || oferta.checkout_mode !== "automatic") {
    throw new Error("A oferta para esta competência ainda não está disponível.")
  }
}

function validarCompra(compra, competencia) {
  if (!compra || compra.competencia !== competencia
      || !chaveValida(compra.checkout_idempotency_key)
      || !["paid", "pending"].includes(compra.estado)
      || (compra.estado === "paid" && (compra.autorizado !== true || compra.checkout_url !== null))
      || (compra.estado === "pending" && (compra.autorizado !== false
          || (compra.checkout_url !== null && !urlSegura(compra.checkout_url))))) {
    throw new Error("Não foi possível confirmar a compra desta competência.")
  }
  return compra
}

export function criarMeiCompetenciaCheckout({ baseUrl, fetchAutenticado, storage, randomUUID }) {
  async function request(url, options) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 15000)
    try {
      return await fetchAutenticado(url, { ...options, signal: controller.signal })
    } finally { clearTimeout(timer) }
  }

  async function obterOferta() {
    const res = await request(`${baseUrl}/checkout/offers`, { method: "GET", cache: "no-store" })
    if (!res?.ok) throw new Error("Não foi possível consultar a oferta MEI.")
    const ofertas = await res.json()
    if (!Array.isArray(ofertas)) throw new Error("Catálogo MEI indisponível.")
    const selecionadas = ofertas.filter(item => item?.offer_code === OFFER_CODE)
    if (selecionadas.length === 0) return null
    if (selecionadas.length !== 1) throw new Error("Catálogo MEI indisponível.")
    validarOferta(selecionadas[0])
    return selecionadas[0]
  }

  async function recuperar(scope) {
    validarEscopo(scope)
    const { empresaId, competencia } = scope
    const res = await request(
      `${baseUrl}/imposto/mei/${empresaId}/checkout-recovery?competencia=${competencia}`,
      { method: "GET", cache: "no-store" },
    )
    if (res?.status === 404) return null
    if (!res?.ok) throw new Error("Não foi possível confirmar a compra. Atualize antes de tentar pagar.")
    return validarCompra(await res.json(), competencia)
  }

  async function iniciar({ empresaId, competencia, oferta }) {
    validarEscopo({ empresaId, competencia })
    // Read again at purchase time; a stale screen never authorizes a new charge.
    const compra = await recuperar({ empresaId, competencia })
    if (compra?.estado === "paid" || compra?.checkout_url) return compra
    validarOferta(oferta)

    const storageKey = `solveris.meiCompetenciaCheckout.v1:${empresaId}:${competencia}`
    let idempotencyKey = compra?.checkout_idempotency_key
    try {
      idempotencyKey ||= storage.getItem(storageKey)
      if (!chaveValida(idempotencyKey)) idempotencyKey = randomUUID()
      if (!chaveValida(idempotencyKey)) throw new Error()
      storage.setItem(storageKey, idempotencyKey)
    } catch {
      throw new Error("Não foi possível guardar a tentativa de compra. Nenhuma nova cobrança foi iniciada.")
    }

    const headers = { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey }
    const intent = await request(`${baseUrl}/imposto/mei/${empresaId}/checkout-intents`, {
      method: "POST", headers,
      body: JSON.stringify({ competencia, offer_code: OFFER_CODE }),
    })
    if (intent?.status !== 204) throw new Error("Não foi possível preparar a compra desta competência.")

    const checkout = await request(`${baseUrl}/checkout/one-time`, {
      method: "POST", headers,
      body: JSON.stringify({ empresa_id: empresaId, offer_code: OFFER_CODE }),
    })
    if (!checkout?.ok) throw new Error("Checkout não confirmado. Atualize para recuperar a tentativa antes de pagar.")
    const payload = await checkout.json()
    if (!urlSegura(payload?.checkout_url)) throw new Error("Link de pagamento indisponível.")
    return {
      estado: "pending", competencia, autorizado: false,
      checkout_idempotency_key: idempotencyKey, checkout_url: payload.checkout_url,
    }
  }

  return { obterOferta, recuperar, iniciar }
}

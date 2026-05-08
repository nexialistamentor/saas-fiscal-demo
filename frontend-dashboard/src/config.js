const raw = import.meta.env.VITE_API_URL;

if (!raw) {
  throw new Error("VITE_API_URL não definida no build");
}

export const API_BASE = String(raw).replace(/\/$/, "");

const TOKEN_KEY = "auth_token"

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  return localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  return localStorage.removeItem(TOKEN_KEY)
}

export function isAuthenticated() {
  return !!localStorage.getItem(TOKEN_KEY)
}

export async function logout() {
  try {
    await fetchAutenticado(`${API_BASE}/auth/logout`, { method: "POST" })
  } catch (err) {
    // ignora erro — limpa token na mesma
  } finally {
    clearToken()
  }
}

export async function login(email, password) {
  const form = new URLSearchParams()
  form.append("username", email)
  form.append("password", password)

  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded"
    },
    body: form
  })

  if (!res.ok) {
    throw new Error("Login inválido")
  }

  const data = await res.json()

  setToken(data.access_token)

  return data
}

/**
 * fetchAutenticado — wrapper global para todos os pedidos autenticados.
 * Trata 401 automaticamente: limpa token e redireciona para login.
 */
export async function fetchAutenticado(url, opcoes = {}) {
  const token = getToken()
  const headers = {
    ...opcoes.headers,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }

  const res = await fetch(url, { ...opcoes, headers })

  if (res.status === 401) {
    clearToken()
    window.location.href = '/login'
    return null
  }

  return res
}

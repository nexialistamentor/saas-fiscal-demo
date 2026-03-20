const raw = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"
export const API_BASE = String(raw).replace(/\/$/, "")

const TOKEN_KEY = "auth_token"
export const DEMO_TOKEN = "demo_admin"

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export function isAuthenticated() {
  return !!localStorage.getItem(TOKEN_KEY)
}

export function isDemoSession(token = getToken()) {
  return token === DEMO_TOKEN
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

export function loginDemo() {
  setToken(DEMO_TOKEN)
}

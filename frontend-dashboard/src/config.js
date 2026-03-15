export const API_BASE = "http://127.0.0.1:8000"

export function getToken() {
  return (
    localStorage.getItem("auth_token") ||
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZW1vQGxvY2FsLmRldiIsImV4cCI6MTc3MzYxNzcyMX0.xdk7-P6nqyKlJZRm-M-AIsLf0mqOX__gBiDIFjCiCZg"
  )
}

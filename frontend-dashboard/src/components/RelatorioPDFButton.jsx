import React, { useState } from "react"
import { API_BASE, getToken } from "../config"

export default function RelatorioPDFButton({ idPerfil }) {
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState(null)

  async function baixarPDF() {
    setLoading(true)
    setErro(null)
    try {
      const TOKEN = getToken()
      const res = await fetch(`${API_BASE}/relatorio/gerar`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${TOKEN}`,
        },
        body: JSON.stringify({ perfil_id: idPerfil }),
      })
      if (!res.ok) {
        if (res.status === 402 || res.status === 403) {
          const err = await res.json().catch(() => ({}))
          setErro(err.detail || "Pagamento necessário para acessar o relatório.")
        } else {
          setErro("Não foi possível baixar o relatório.")
        }
        return
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = "relatorio-fiscal.pdf"
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setErro("Erro ao baixar o PDF.")
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relatorio-pdf-wrap">
      <button
        type="button"
        className="btn-baixar-pdf"
        onClick={baixarPDF}
        disabled={loading}
      >
        {loading ? "Gerando PDF..." : "Baixar Relatório PDF"}
      </button>
      {erro && <span className="relatorio-pdf-erro">{erro}</span>}
    </div>
  )
}

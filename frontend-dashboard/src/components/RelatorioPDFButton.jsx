import React, { useState } from "react"
import { API_BASE, getToken } from "../config"

export default function RelatorioPDFButton({
  empresaId,
  acquisitionId,
}) {
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState(null)

  async function baixarPDF() {
    setLoading(true)
    setErro(null)
    try {
      if (
        !Number.isInteger(empresaId) ||
        empresaId <= 0 ||
        !Number.isInteger(acquisitionId) ||
        acquisitionId <= 0
      ) {
        setErro("Relatório adquirido indisponível.")
        return
      }

      const res = await fetch(
        `${API_BASE}/relatorio/empresas/${empresaId}/acquisitions/${acquisitionId}/pdf`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${getToken()}`,
          },
        }
      )
      if (!res.ok) {
        setErro("Não foi possível baixar o relatório.")
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

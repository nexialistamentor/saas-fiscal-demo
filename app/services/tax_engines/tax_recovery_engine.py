from app.services.tax_engines.base_tax_engine import BaseTaxEngine


class TaxRecoveryEngine(BaseTaxEngine):
    """
    Engine de recuperação tributária.
    Detecta oportunidades de recuperação de impostos.
    """

    name = "tax_recovery"

    def execute(self, context: dict):
        creditos = []

        icms_pago = context.get("icms_pago", 0)
        icms_devido = context.get("icms_devido", 0)

        if icms_pago > icms_devido:
            creditos.append({
                "tipo": "ICMS_RECUPERAVEL",
                "origem": "icms_fluxo",
                "valor": icms_pago - icms_devido
            })

        return {
            "creditos_identificados": creditos,
            "total_creditos": sum(c["valor"] for c in creditos) if creditos else 0
        }

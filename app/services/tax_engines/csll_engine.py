from app.services.tax_engines.base_tax_engine import BaseTaxEngine

# Alíquota legal da CSLL sobre a base de cálculo (pessoa jurídica em geral — Lucro Real ou presumido).
ALIQUOTA_CSLL = 0.09


class CSLLEngine(BaseTaxEngine):
    def execute(self, context: dict):
        """
        Aplica 9% sobre a base informada em ``context["lucro"]``.

        Este motor não distingue regime: quem chama deve passar a base já adequada —
        lucro contábil (Lucro Real) ou margem presumida 12% comércio/indústria / 32%
        serviços sobre o faturamento (Lucro Presumido), conforme ``lucro_presumido_engine``.
        """
        raw = context.get("lucro", 0)
        try:
            base = max(0.0, float(raw or 0))
        except (TypeError, ValueError):
            base = 0.0

        csll = base * ALIQUOTA_CSLL

        return {
            "tributo": "CSLL",
            "valor": csll,
        }

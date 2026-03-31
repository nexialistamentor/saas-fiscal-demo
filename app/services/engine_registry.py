from app.services.tax_engines.tax_planning_engine import simular_regimes, TaxPlanningEngine
from app.services.tax_engines.tax_recovery_engine import TaxRecoveryEngine
from app.services.tax_engines.regime_router import calcular_impostos_empresa
from app.services.tax_engines.irpj_engine import IRPJEngine
from app.services.tax_engines.csll_engine import CSLLEngine
from app.services.tax_engines.pis_cofins_engine import PISCOFINSEngine
from app.services.tax_engines.lucro_real_engine import LucroRealEngine
from app.services.tax_engines.mei_engine import MEIEngine

# Registro de todas as engines BaseTaxEngine para execução direta
ENGINES = {
    "irpj": IRPJEngine(),
    "csll": CSLLEngine(),
    "pis_cofins": PISCOFINSEngine(),
    "lucro_real": LucroRealEngine(),
    "mei": MEIEngine(),
    "tax_planning": TaxPlanningEngine(),
    "tax_recovery": TaxRecoveryEngine()
}

ENGINE_REGISTRY = {
    "tax_planning": {
        "v1": simular_regimes
    },
    "tax_recovery": {
        "v1": lambda dados: TaxRecoveryEngine().execute(dados)
    },
    "empresa_tax": {
        "v1": calcular_impostos_empresa
    }
}

from types import MappingProxyType

from app.services.analysis_types import (
    ANALYSIS_TYPE_TAX_PLANNING,
    ANALYSIS_TYPE_TAX_RECOVERY,
    ANALYSIS_TYPE_EMPRESA_TAX,
    ANALYSIS_TYPE_CPF_TAX,
    ANALYSIS_TYPE_MEI_TAX,
)
from app.services.tax_engines.tax_planning_engine import simular_regimes, TaxPlanningEngine
from app.services.tax_engines.tax_recovery_engine import TaxRecoveryEngine
from app.services.tax_engines.regime_router import calcular_impostos_empresa
from app.services.tax_engines.irpj_engine import IRPJEngine
from app.services.tax_engines.csll_engine import CSLLEngine
from app.services.tax_engines.pis_cofins_engine import PISCOFINSEngine
from app.services.tax_engines.lucro_real_engine import LucroRealEngine
from app.services.tax_engines.lucro_presumido_engine import LucroPresumidoEngine
from app.services.tax_engines.cpf_tax_engine import CPFTaxEngine
from app.services.tax_engines.mei_tax_engine import MEITaxEngine

# Registro de todas as engines BaseTaxEngine para execução direta (somente leitura)
_ENGINES_RAW = {
    "irpj": IRPJEngine(),
    "csll": CSLLEngine(),
    "pis_cofins": PISCOFINSEngine(),
    "lucro_real": LucroRealEngine(),
    "lucro_presumido": LucroPresumidoEngine(),
    ANALYSIS_TYPE_TAX_PLANNING: TaxPlanningEngine(),
    ANALYSIS_TYPE_TAX_RECOVERY: TaxRecoveryEngine(),
    ANALYSIS_TYPE_CPF_TAX: CPFTaxEngine(),
    ANALYSIS_TYPE_MEI_TAX: MEITaxEngine(),
}
ENGINES = MappingProxyType(_ENGINES_RAW)


def _execute_engine_v1(tipo_analise: str):
    def _run(dados: dict):
        return ENGINES[tipo_analise].execute(dados)

    return _run


_ENGINE_REGISTRY_RAW = {
    ANALYSIS_TYPE_TAX_PLANNING: {
        "v1": simular_regimes
    },
    ANALYSIS_TYPE_TAX_RECOVERY: {
        "v1": _execute_engine_v1(ANALYSIS_TYPE_TAX_RECOVERY)
    },
    ANALYSIS_TYPE_EMPRESA_TAX: {
        "v1": calcular_impostos_empresa
    },
    ANALYSIS_TYPE_CPF_TAX: {
        "v1": _execute_engine_v1(ANALYSIS_TYPE_CPF_TAX)
    },
    ANALYSIS_TYPE_MEI_TAX: {
        "v1": _execute_engine_v1(ANALYSIS_TYPE_MEI_TAX)
    },
}

ENGINE_REGISTRY = MappingProxyType(
    {k: MappingProxyType(v) for k, v in _ENGINE_REGISTRY_RAW.items()}
)

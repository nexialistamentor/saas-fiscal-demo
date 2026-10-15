"""M006-C2: contrato puro de indicadores agregados de seguranca."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class SecurityAuditContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_kind: Literal["enterprise_aggregated_request_logs"]
    window_minutes: Literal[60]
    max_distinct_accounts_per_ip: StrictInt = Field(ge=0, le=1_000_000)
    max_requests_per_user: StrictInt = Field(ge=0, le=1_000_000)
    requests_without_user_agent: StrictInt = Field(ge=0, le=1_000_000)

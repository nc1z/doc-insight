from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UsageCall(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    document_id: UUID | None
    model: str
    prompt_id: str
    prompt_version: int
    input_tokens: int
    output_tokens: int
    latency_ms: int


class UsageTotals(BaseModel):
    calls: int
    input_tokens: int
    output_tokens: int
    latency_ms: int


class UsageView(BaseModel):
    calls: list[UsageCall]
    totals: UsageTotals

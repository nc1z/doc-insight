from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.adapters.factory import get_job_repository
from app.core.errors import DomainError, ErrorBody
from app.domain.ports import JobRepository
from app.schemas.admin import UsageCall, UsageTotals, UsageView

router = APIRouter()


@router.get("/admin/usage", response_model=UsageView, responses={404: {"model": ErrorBody}})
async def read_usage(
    jobs: Annotated[JobRepository, Depends(get_job_repository)],
    job_id: UUID | None = None,
) -> UsageView:
    if job_id is not None and await jobs.get(job_id) is None:
        raise DomainError(404, "not_found", "The job was not found.")
    rows = await jobs.list_llm_calls(job_id)
    return UsageView(
        calls=[UsageCall.model_validate(row, from_attributes=True) for row in rows],
        totals=UsageTotals(
            calls=len(rows),
            input_tokens=sum(row.input_tokens for row in rows),
            output_tokens=sum(row.output_tokens for row in rows),
            latency_ms=sum(row.latency_ms for row in rows),
        ),
    )

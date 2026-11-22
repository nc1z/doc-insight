import pytest

from app.core.errors import DomainError
from app.domain.job_state import transition
from app.domain.status import JobStatus

_ALLOWED = {
    (JobStatus.AWAITING_INPUT, JobStatus.AWAITING_INPUT),
    (JobStatus.AWAITING_INPUT, JobStatus.QUEUED),
    (JobStatus.AWAITING_INPUT, JobStatus.CANCELLED),
    (JobStatus.AWAITING_INPUT, JobStatus.EXPIRED),
    (JobStatus.QUEUED, JobStatus.RUNNING),
    (JobStatus.RUNNING, JobStatus.CONSOLIDATING),
    (JobStatus.RUNNING, JobStatus.FAILED),
    (JobStatus.CONSOLIDATING, JobStatus.SUCCEEDED),
    (JobStatus.CONSOLIDATING, JobStatus.FAILED),
}


@pytest.mark.parametrize(("current", "target"), sorted(_ALLOWED))
def test_allowed_transition(current: JobStatus, target: JobStatus) -> None:
    assert transition(current, target) == target


_CONFLICTS = [
    (current, target)
    for current in JobStatus
    for target in JobStatus
    if (current, target) not in _ALLOWED
]


@pytest.mark.parametrize(("current", "target"), _CONFLICTS)
def test_other_transitions_conflict(current: JobStatus, target: JobStatus) -> None:
    with pytest.raises(DomainError) as caught:
        transition(current, target)

    error = caught.value
    assert error.status_code == 409
    assert error.code == "invalid_job_state"
    assert error.message == f"The job cannot move from {current} to {target}."
    assert error.details == {"from": current.value, "to": target.value}

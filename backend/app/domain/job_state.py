from app.core.errors import DomainError
from app.domain.status import JobStatus

_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.AWAITING_INPUT: frozenset(
        {
            JobStatus.AWAITING_INPUT,
            JobStatus.QUEUED,
            JobStatus.CANCELLED,
            JobStatus.EXPIRED,
        }
    ),
    JobStatus.QUEUED: frozenset({JobStatus.RUNNING}),
    JobStatus.RUNNING: frozenset({JobStatus.CONSOLIDATING, JobStatus.FAILED}),
    JobStatus.CONSOLIDATING: frozenset({JobStatus.SUCCEEDED, JobStatus.FAILED}),
    JobStatus.SUCCEEDED: frozenset(),
    JobStatus.FAILED: frozenset(),
    JobStatus.CANCELLED: frozenset(),
    JobStatus.EXPIRED: frozenset(),
}


def transition(current: JobStatus, target: JobStatus) -> JobStatus:
    if target not in _TRANSITIONS[current]:
        raise DomainError(
            409,
            "invalid_transition",
            f"The job cannot move from {current} to {target}.",
            {"from": current.value, "to": target.value},
        )
    return target

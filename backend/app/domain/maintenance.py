from datetime import UTC, datetime

from app.domain.ports import FileStorage, JobRepository


async def expire_waiting_jobs(
    jobs: JobRepository,
    storage: FileStorage,
    *,
    older_than: datetime,
) -> None:
    for key in await jobs.expire_awaiting(older_than):
        await storage.delete(key)


async def delete_orphan_files(
    jobs: JobRepository,
    storage: FileStorage,
    *,
    older_than: datetime,
) -> None:
    referenced = await jobs.storage_keys()
    for obj in await storage.list_objects():
        modified = obj.last_modified
        if modified.tzinfo is None:
            modified = modified.replace(tzinfo=UTC)
        if obj.key not in referenced and modified < older_than:
            await storage.delete(obj.key)

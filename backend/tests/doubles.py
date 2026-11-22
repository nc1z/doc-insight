from app.domain.ports import StoredObject


class IdleFileStorage:
    """Storage stand-in so API tests can start without MinIO."""

    async def ensure_bucket(self) -> None:
        return None

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        return None

    async def get(self, key: str) -> bytes:
        raise FileNotFoundError(key)

    async def delete(self, key: str) -> None:
        return None

    async def list_objects(self) -> list[StoredObject]:
        return []

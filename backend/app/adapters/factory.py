from collections.abc import Callable

from fastapi import Request

from app.adapters.s3 import S3FileStorage
from app.core.config import Settings
from app.domain.ports import FileStorage

StorageBuilder = Callable[[Settings], FileStorage]

_ADAPTERS: dict[str, StorageBuilder] = {
    "s3": S3FileStorage.from_settings,
}


def register_storage_adapter(provider: str, builder: StorageBuilder) -> None:
    _ADAPTERS[provider] = builder


def build_file_storage(settings: Settings) -> FileStorage:
    try:
        builder = _ADAPTERS[settings.storage_provider]
    except KeyError:
        raise ValueError(f"Unknown storage provider: {settings.storage_provider}") from None
    return builder(settings)


def get_file_storage(request: Request) -> FileStorage:
    return request.app.state.file_storage

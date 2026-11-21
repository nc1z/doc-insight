from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

_UNTYPED_MEDIA_TYPES = frozenset({"", "application/octet-stream"})
_PDF_HEADER = b"%PDF"
_JAVASCRIPT_KEYS = {"/JavaScript", "/JS"}


class FileErrorCode(StrEnum):
    UNSUPPORTED_TYPE = "unsupported_type"
    INVALID_PDF = "invalid_pdf"
    ENCRYPTED_PDF = "encrypted_pdf"
    ACTIVE_CONTENT = "active_content"
    EMBEDDED_FILE = "embedded_file"
    FILE_TOO_LARGE = "file_too_large"
    PAGE_LIMIT_EXCEEDED = "page_limit_exceeded"
    FILE_COUNT_EXCEEDED = "file_count_exceeded"


_MESSAGES = {
    FileErrorCode.UNSUPPORTED_TYPE: "The file is not a PDF.",
    FileErrorCode.INVALID_PDF: "The PDF is corrupt or cannot be parsed.",
    FileErrorCode.ENCRYPTED_PDF: "The PDF is password-protected.",
    FileErrorCode.ACTIVE_CONTENT: "The PDF contains JavaScript.",
    FileErrorCode.EMBEDDED_FILE: "The PDF contains embedded files.",
    FileErrorCode.FILE_TOO_LARGE: "The file is over the size limit.",
    FileErrorCode.PAGE_LIMIT_EXCEEDED: "The PDF has more pages than allowed.",
    FileErrorCode.FILE_COUNT_EXCEEDED: "The upload has more files than allowed.",
}


@dataclass(frozen=True)
class IncomingFile:
    filename: str
    content_type: str
    data: bytes


@dataclass(frozen=True)
class FileRejection:
    filename: str
    code: FileErrorCode
    message: str


@dataclass(frozen=True)
class AcceptedFile:
    filename: str
    data: bytes
    page_count: int | None = None


@dataclass(frozen=True)
class UploadError:
    code: FileErrorCode
    message: str


@dataclass(frozen=True)
class UploadValidation:
    accepted: tuple[AcceptedFile, ...]
    rejected: tuple[FileRejection, ...]
    error: UploadError | None = None


@dataclass
class FileState:
    file: IncomingFile
    page_count: int | None = None
    recognized: bool = False


class ValidationStrategy:
    """One step in the list passed to `validate_files`. Steps run in order."""

    def check_upload(self, files: Sequence[IncomingFile]) -> UploadError | None:
        return None

    def check(self, state: FileState) -> FileRejection | None:
        return None


class FileValidation(ValidationStrategy):
    """Checks that apply to every upload: how many files, how large each one is, and its type."""

    def __init__(
        self,
        *,
        max_file_bytes: int,
        max_file_count: int,
        allowed_media_types: frozenset[str],
    ) -> None:
        self._max_file_bytes = max_file_bytes
        self._max_file_count = max_file_count
        self._allowed_media_types = allowed_media_types

    def check_upload(self, files: Sequence[IncomingFile]) -> UploadError | None:
        if len(files) > self._max_file_count:
            return UploadError(
                code=FileErrorCode.FILE_COUNT_EXCEEDED,
                message=_MESSAGES[FileErrorCode.FILE_COUNT_EXCEEDED],
            )
        return None

    def check(self, state: FileState) -> FileRejection | None:
        file = state.file
        if len(file.data) > self._max_file_bytes:
            return _rejection(file.filename, FileErrorCode.FILE_TOO_LARGE)
        media_type = _media_type(file.content_type)
        if media_type in self._allowed_media_types or media_type in _UNTYPED_MEDIA_TYPES:
            return None
        return _rejection(file.filename, FileErrorCode.UNSUPPORTED_TYPE)


class PdfValidation(ValidationStrategy):
    """Checks that apply once a file is being read as a PDF."""

    media_types = frozenset({"application/pdf", "application/x-pdf"})

    def __init__(self, *, max_page_count: int) -> None:
        self._max_page_count = max_page_count

    def check(self, state: FileState) -> FileRejection | None:
        file = state.file
        if not self._owns(file):
            return None
        state.recognized = True
        if not file.data.startswith(_PDF_HEADER):
            return _rejection(file.filename, FileErrorCode.UNSUPPORTED_TYPE)
        try:
            reader = PdfReader(BytesIO(file.data))
            if reader.is_encrypted:
                return _rejection(file.filename, FileErrorCode.ENCRYPTED_PDF)
            if _has_javascript(reader):
                return _rejection(file.filename, FileErrorCode.ACTIVE_CONTENT)
            if reader.attachments:
                return _rejection(file.filename, FileErrorCode.EMBEDDED_FILE)
            page_count = len(reader.pages)
        except PdfReadError:
            return _rejection(file.filename, FileErrorCode.INVALID_PDF)
        if page_count > self._max_page_count:
            return _rejection(file.filename, FileErrorCode.PAGE_LIMIT_EXCEEDED)
        if page_count < 1:
            return _rejection(file.filename, FileErrorCode.INVALID_PDF)
        state.page_count = page_count
        return None

    def _owns(self, file: IncomingFile) -> bool:
        media_type = _media_type(file.content_type)
        if media_type in self.media_types:
            return True
        return media_type in _UNTYPED_MEDIA_TYPES and file.data.startswith(_PDF_HEADER)


def validate_files(
    files: Sequence[IncomingFile],
    strategies: Sequence[ValidationStrategy],
) -> UploadValidation:
    for strategy in strategies:
        upload_error = strategy.check_upload(files)
        if upload_error is not None:
            return UploadValidation(accepted=(), rejected=(), error=upload_error)

    accepted: list[AcceptedFile] = []
    rejected: list[FileRejection] = []
    for file in files:
        state = FileState(file)
        rejection = _run_strategies(state, strategies)
        if rejection is not None:
            rejected.append(rejection)
        elif state.recognized:
            accepted.append(
                AcceptedFile(filename=file.filename, data=file.data, page_count=state.page_count)
            )
        else:
            rejected.append(_rejection(file.filename, FileErrorCode.UNSUPPORTED_TYPE))
    return UploadValidation(accepted=tuple(accepted), rejected=tuple(rejected))


def default_strategies(
    *,
    max_file_bytes: int,
    max_page_count: int,
    max_file_count: int,
) -> tuple[ValidationStrategy, ...]:
    pdf = PdfValidation(max_page_count=max_page_count)
    return (
        FileValidation(
            max_file_bytes=max_file_bytes,
            max_file_count=max_file_count,
            allowed_media_types=pdf.media_types,
        ),
        pdf,
    )


def _run_strategies(
    state: FileState,
    strategies: Sequence[ValidationStrategy],
) -> FileRejection | None:
    for strategy in strategies:
        rejection = strategy.check(state)
        if rejection is not None:
            return rejection
    return None


def _rejection(filename: str, code: FileErrorCode) -> FileRejection:
    return FileRejection(filename=filename, code=code, message=_MESSAGES[code])


def _media_type(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()


def _has_javascript(reader: PdfReader) -> bool:
    return _contains_key(reader.root_object, _JAVASCRIPT_KEYS, set())


def _contains_key(value: object, names: set[str], seen: set[int]) -> bool:
    if isinstance(value, IndirectObject):
        value = value.get_object()
    marker = id(value)
    if marker in seen:
        return False
    seen.add(marker)
    if isinstance(value, DictionaryObject):
        for key, item in value.items():
            if str(key) in names or _contains_key(item, names, seen):
                return True
        return False
    if isinstance(value, ArrayObject):
        return any(_contains_key(item, names, seen) for item in value)
    return False

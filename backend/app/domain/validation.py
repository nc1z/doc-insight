from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

_PDF_MEDIA_TYPES = {"application/pdf", "application/x-pdf"}
_UNTYPED_MEDIA_TYPES = {"", "application/octet-stream"}
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
    page_count: int


@dataclass(frozen=True)
class UploadError:
    code: FileErrorCode
    message: str


@dataclass(frozen=True)
class UploadValidation:
    accepted: tuple[AcceptedFile, ...]
    rejected: tuple[FileRejection, ...]
    error: UploadError | None = None


def validate_files(
    files: Sequence[IncomingFile],
    *,
    max_file_bytes: int,
    max_page_count: int,
    max_file_count: int,
) -> UploadValidation:
    if len(files) > max_file_count:
        return UploadValidation(
            accepted=(),
            rejected=(),
            error=UploadError(
                code=FileErrorCode.FILE_COUNT_EXCEEDED,
                message=_MESSAGES[FileErrorCode.FILE_COUNT_EXCEEDED],
            ),
        )

    accepted: list[AcceptedFile] = []
    rejected: list[FileRejection] = []
    for file in files:
        result = _validate_file(file, max_file_bytes=max_file_bytes, max_page_count=max_page_count)
        if isinstance(result, FileRejection):
            rejected.append(result)
        else:
            accepted.append(result)
    return UploadValidation(accepted=tuple(accepted), rejected=tuple(rejected))


def _rejection(filename: str, code: FileErrorCode) -> FileRejection:
    return FileRejection(filename=filename, code=code, message=_MESSAGES[code])


def _validate_file(
    file: IncomingFile,
    *,
    max_file_bytes: int,
    max_page_count: int,
) -> AcceptedFile | FileRejection:
    if len(file.data) > max_file_bytes:
        return _rejection(file.filename, FileErrorCode.FILE_TOO_LARGE)
    if not _declared_pdf(file.content_type) or not file.data.startswith(_PDF_HEADER):
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
    if page_count > max_page_count:
        return _rejection(file.filename, FileErrorCode.PAGE_LIMIT_EXCEEDED)
    if page_count < 1:
        return _rejection(file.filename, FileErrorCode.INVALID_PDF)
    return AcceptedFile(filename=file.filename, data=file.data, page_count=page_count)


def _declared_pdf(content_type: str) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type in _PDF_MEDIA_TYPES or media_type in _UNTYPED_MEDIA_TYPES


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

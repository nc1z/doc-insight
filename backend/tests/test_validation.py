from io import BytesIO

from pypdf import PdfWriter
from pypdf.actions import JavaScript

from app.domain.validation import (
    FileErrorCode,
    FileRejection,
    FileState,
    IncomingFile,
    ValidationStrategy,
    default_strategies,
    validate_files,
)

_LIMITS = {"max_file_bytes": 1024 * 1024, "max_page_count": 2, "max_file_count": 2}


def _pdf(
    *, javascript: str | None = None, attachment: bytes | None = None, pages: int = 1
) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    if javascript is not None:
        writer.add_open_action(JavaScript(javascript))
    if attachment is not None:
        writer.add_attachment("payload.exe", attachment)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _file(
    data: bytes, filename: str = "notes.pdf", content_type: str = "application/pdf"
) -> IncomingFile:
    return IncomingFile(filename=filename, content_type=content_type, data=data)


def _validate(*files: IncomingFile, **limits: int):
    settings = {**_LIMITS, **limits}
    return validate_files(files, default_strategies(**settings))


class TestStrategies:
    def test_strategies_run_in_order_and_stop_on_rejection(self) -> None:
        seen: list[str] = []

        class RecordingStrategy(ValidationStrategy):
            def __init__(self, name: str, *, reject: bool) -> None:
                self._name = name
                self._reject = reject

            def check(self, state: FileState) -> FileRejection | None:
                seen.append(self._name)
                if self._reject:
                    return FileRejection(
                        filename=state.file.filename,
                        code=FileErrorCode.UNSUPPORTED_TYPE,
                        message="The file is not a PDF.",
                    )
                return None

        result = validate_files(
            [_file(_pdf())],
            [RecordingStrategy("first", reject=True), RecordingStrategy("second", reject=False)],
        )

        assert seen == ["first"]
        assert result.rejected[0].filename == "notes.pdf"

    def test_mixed_upload_keeps_valid_files(self) -> None:
        result = _validate(
            _file(_pdf(), "ok.pdf"),
            _file(b"notes", "notes.pdf", "text/plain"),
        )

        assert result.error is None
        assert [item.filename for item in result.accepted] == ["ok.pdf"]
        assert [item.code for item in result.rejected] == [FileErrorCode.UNSUPPORTED_TYPE]


class TestFileValidation:
    def test_too_many_files_rejects_the_upload(self) -> None:
        result = _validate(_file(_pdf(), "a.pdf"), _file(_pdf(), "b.pdf"), _file(_pdf(), "c.pdf"))

        assert result.accepted == ()
        assert result.rejected == ()
        assert result.error is not None
        assert result.error.code is FileErrorCode.FILE_COUNT_EXCEEDED
        assert result.error.message == "The upload has more files than allowed."

    def test_size_is_checked_before_the_file_type(self) -> None:
        data = b"These are plain-text meeting notes saved with a .pdf extension."
        result = _validate(_file(data, content_type="text/plain"), max_file_bytes=8)

        assert result.rejected[0].code is FileErrorCode.FILE_TOO_LARGE

    def test_over_size_limit_is_rejected_before_parsing(self) -> None:
        result = _validate(_file(_pdf(), filename="oversized.pdf"), max_file_bytes=8)

        assert result.rejected[0].code is FileErrorCode.FILE_TOO_LARGE
        assert result.rejected[0].message == "The file is over the size limit."

    def test_plain_text_renamed_as_pdf_is_rejected(self) -> None:
        data = b"These are plain-text meeting notes saved with a .pdf extension."
        result = _validate(_file(data, content_type="text/plain"))

        assert result.accepted == ()
        assert result.rejected[0].code is FileErrorCode.UNSUPPORTED_TYPE
        assert result.rejected[0].message == "The file is not a PDF."

    def test_declared_non_pdf_type_is_rejected_even_with_header(self) -> None:
        result = _validate(_file(_pdf(), content_type="text/plain"))

        assert result.rejected[0].code is FileErrorCode.UNSUPPORTED_TYPE


class TestPdfValidation:
    def test_valid_pdf_is_accepted(self) -> None:
        result = _validate(_file(_pdf()))

        assert result.error is None
        assert result.rejected == ()
        assert result.accepted[0].page_count == 1
        assert result.accepted[0].filename == "notes.pdf"

    def test_octet_stream_with_pdf_header_is_accepted(self) -> None:
        result = _validate(_file(_pdf(), content_type="application/octet-stream"))

        assert result.rejected == ()
        assert len(result.accepted) == 1

    def test_pdf_media_type_without_header_is_rejected(self) -> None:
        result = _validate(_file(b"not really a pdf"))

        assert result.rejected[0].code is FileErrorCode.UNSUPPORTED_TYPE

    def test_truncated_pdf_is_rejected(self) -> None:
        data = _pdf()
        result = _validate(_file(data[: len(data) // 3], filename="corrupt.pdf"))

        assert result.rejected[0].code is FileErrorCode.INVALID_PDF
        assert result.rejected[0].message == "The PDF is corrupt or cannot be parsed."

    def test_encrypted_pdf_is_rejected(self) -> None:
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.encrypt("harbour")
        buffer = BytesIO()
        writer.write(buffer)

        result = _validate(_file(buffer.getvalue(), filename="encrypted.pdf"))

        assert result.rejected[0].code is FileErrorCode.ENCRYPTED_PDF
        assert result.rejected[0].message == "The PDF is password-protected."

    def test_javascript_pdf_is_rejected(self) -> None:
        result = _validate(_file(_pdf(javascript="app.alert('Hello');"), filename="javascript.pdf"))

        assert result.rejected[0].code is FileErrorCode.ACTIVE_CONTENT
        assert result.rejected[0].message == "The PDF contains JavaScript."

    def test_embedded_file_is_rejected(self) -> None:
        result = _validate(_file(_pdf(attachment=b"MZ"), filename="embedded-file.pdf"))

        assert result.rejected[0].code is FileErrorCode.EMBEDDED_FILE
        assert result.rejected[0].message == "The PDF contains embedded files."

    def test_too_many_pages_is_rejected(self) -> None:
        result = _validate(_file(_pdf(pages=3), filename="too-many-pages.pdf"))

        assert result.rejected[0].code is FileErrorCode.PAGE_LIMIT_EXCEEDED
        assert result.rejected[0].message == "The PDF has more pages than allowed."

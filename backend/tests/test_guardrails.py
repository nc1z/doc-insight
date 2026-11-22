from io import BytesIO

from reportlab.lib import colors
from reportlab.pdfgen import canvas

from app.pipeline.guardrails import scan_pdf
from evals.builder import FixtureLimits, build_fixture

_LIMITS = FixtureLimits(20 * 1024 * 1024, 100, 10)


def test_a_plain_page_has_no_findings() -> None:
    assert scan_pdf(_fixture("community-feedback")) == []


def test_an_injection_phrase_is_recorded_on_its_page() -> None:
    findings = scan_pdf(_fixture("feedback-direct-injection"))

    assert [(item.page_number, item.rule) for item in findings] == [(2, "injection_pattern")]
    assert "ignore all previous instructions" in findings[0].excerpt.lower()


def test_a_document_that_discusses_injection_still_records_the_phrase() -> None:
    findings = scan_pdf(_fixture("security-explainer"))

    assert [(item.page_number, item.rule) for item in findings] == [(1, "injection_pattern")]


def test_a_speaker_label_is_not_a_role_marker() -> None:
    assert scan_pdf(_fixture("meeting-transcript")) == []


def test_fake_role_markers_are_recorded() -> None:
    findings = scan_pdf(_fixture("feedback-fake-delimiters"))

    assert {(item.page_number, item.rule) for item in findings} == {(2, "role_marker")}
    assert any("</document>" in item.excerpt for item in findings)
    assert any("SYSTEM:" in item.excerpt for item in findings)


def test_white_or_tiny_text_is_hidden_text() -> None:
    hidden = scan_pdf(_fixture("feedback-hidden-text"))
    assert any(item.rule == "hidden_text" and item.page_number == 2 for item in hidden)
    assert any("cancelled" in item.excerpt for item in hidden)

    white = scan_pdf(_drawn("See you Monday.", 11, colors.white))
    tiny = scan_pdf(_drawn("See you Monday.", 1, colors.black))
    assert [item.rule for item in white] == ["hidden_text"]
    assert [item.rule for item in tiny] == ["hidden_text"]


def test_invisible_characters_are_recorded() -> None:
    findings = scan_pdf(_fixture("feedback-invisible-characters"))

    assert [(item.page_number, item.rule) for item in findings] == [(2, "invisible_characters")]
    assert "instructions" in findings[0].excerpt


def test_a_long_encoded_blob_is_recorded() -> None:
    findings = scan_pdf(_fixture("feedback-encoded-blob"))

    assert [(item.page_number, item.rule) for item in findings] == [(2, "encoded_blob")]


def _fixture(name: str) -> bytes:
    return build_fixture(name, _LIMITS).data


def _drawn(text: str, size: float, color: colors.Color) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(612, 792))
    pdf.setFillColor(color)
    pdf.setFont("Times-Roman", size)
    pdf.drawString(72, 720, text)
    pdf.save()
    return buffer.getvalue()

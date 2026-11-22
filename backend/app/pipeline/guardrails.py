"""Programmatic checks. Each finding names the page and the rule."""

import re
from dataclasses import dataclass

import pymupdf

_EXCERPT = 240
_INJECTION = re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE)
_ROLE = re.compile(
    r"</(?:document|data|instructions|system)>|\bSYSTEM\s*:|\bAssistant\s*:",
    re.IGNORECASE,
)
_BLOB = re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{64,}={0,2}")
_ZERO_WIDTH = frozenset({0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF})
_TAG_START = 0xE0000
_TAG_END = 0xE007F


# Hidden text, invisible characters, and encoded blobs flag on their own.
# A phrase or a role marker is stored and does not.
ALONE_RULES = frozenset({"hidden_text", "invisible_characters", "encoded_blob"})
FLAG_REASONS = frozenset({*ALONE_RULES, "classifier"})


@dataclass(frozen=True)
class GuardrailFinding:
    page_number: int
    rule: str
    excerpt: str


def scan_pdf(data: bytes) -> list[GuardrailFinding]:
    document = pymupdf.open(stream=data, filetype="pdf")
    try:
        findings: list[GuardrailFinding] = []
        for index in range(document.page_count):
            findings.extend(_page(index + 1, document[index]))
        return findings
    finally:
        document.close()


def _page(number: int, page: pymupdf.Page) -> list[GuardrailFinding]:
    findings = list(_text_findings(number, page.get_text("text")))
    hidden: list[str] = []
    invisible: list[str] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = str(span.get("text", ""))
                if not text.strip() and not _has_invisible(text):
                    continue
                if _has_invisible(text):
                    invisible.append(text)
                    continue
                if _is_hidden(span):
                    hidden.append(text.strip())
    findings.extend(GuardrailFinding(number, "hidden_text", _clip(text)) for text in hidden if text)
    decoded = _decode_invisible("".join(invisible)).strip()
    if invisible:
        findings.append(
            GuardrailFinding(
                number,
                "invisible_characters",
                _clip(decoded or "zero-width characters"),
            )
        )
    return findings


def _text_findings(number: int, text: str) -> list[GuardrailFinding]:
    findings: list[GuardrailFinding] = []
    for pattern, rule in (
        (_INJECTION, "injection_pattern"),
        (_ROLE, "role_marker"),
        (_BLOB, "encoded_blob"),
    ):
        findings.extend(
            GuardrailFinding(number, rule, _clip(match.group(0)))
            for match in pattern.finditer(text)
        )
    return findings


def _is_hidden(span: dict[str, object]) -> bool:
    size = span.get("size", 0)
    if isinstance(size, int | float) and 0 < size <= 2:
        return True
    color = span.get("color")
    if not isinstance(color, int):
        return False
    return min((color >> 16) & 255, (color >> 8) & 255, color & 255) >= 240


def _has_invisible(text: str) -> bool:
    return any(_invisible(ord(char)) for char in text)


def _invisible(code: int) -> bool:
    return code in _ZERO_WIDTH or _TAG_START <= code <= _TAG_END


def _decode_invisible(text: str) -> str:
    chars: list[str] = []
    for char in text:
        code = ord(char)
        if _TAG_START <= code <= _TAG_END:
            plain = code - _TAG_START
            if 32 <= plain <= 126:
                chars.append(chr(plain))
        elif code not in _ZERO_WIDTH:
            chars.append(char)
    return "".join(chars)


def _clip(text: str) -> str:
    return text if len(text) <= _EXCERPT else text[:_EXCERPT]

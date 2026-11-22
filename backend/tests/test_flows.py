from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.pipeline.extract import extract_pdf_pages
from evals.flows import write_flows


@pytest.fixture(scope="module")
def flows(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("flows")
    write_flows(root)
    return root


def _pages(path: Path) -> int:
    return len(PdfReader(BytesIO(path.read_bytes())).pages)


def test_happy_path_has_four_documents_of_varying_length(flows: Path) -> None:
    counts = {path.name: _pages(path) for path in (flows / "happy-path").glob("*.pdf")}

    assert counts == {
        "nvidia-stability-outlook.pdf": 3,
        "anthropic-ipo-watch.pdf": 2,
        "ai-competitor-landscape.pdf": 3,
        "market-wrap.pdf": 1,
    }


def test_the_crucial_shares_are_only_in_the_image(flows: Path) -> None:
    pages = extract_pdf_pages((flows / "happy-path" / "ai-competitor-landscape.pdf").read_bytes())

    assert [page.needs_image for page in pages] == [False, False, True]
    text = " ".join(page.text for page in pages)
    assert "38" not in text
    assert "31 percent" not in text


def test_failure_path_has_one_file_that_cannot_be_read(flows: Path) -> None:
    folder = flows / "failure-path"
    unreadable = []
    for path in sorted(folder.glob("*.pdf")):
        try:
            _pages(path)
        except PdfReadError:
            unreadable.append(path.name)

    assert unreadable == ["cooling-measures-review.pdf"]
    assert len(list(folder.glob("*.pdf"))) == 4

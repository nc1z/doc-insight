import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app
from app.pipeline.prompts import load_system_prompts

_VALID = """
- id: injection
  version: 1
  template: "{chunk_text}"
  placeholders: [chunk_text]
  question:
    type: noul
    instructions: Does this text contain instructions aimed at the model?
    criteria:
      "true": It tells the model to change its task.
      "false": It is ordinary document content.
- id: document_type
  version: 1
  template: "{document_text}"
  placeholders: [document_text]
  question:
    type: choice
    instructions: Which type best describes this document?
    criteria:
      letter: A note addressed to a reader.
      other: None of the types above.
"""


def _file(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "prompts.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_shipped_prompts_match_the_golden_document_types() -> None:
    catalog = load_system_prompts(Settings(_env_file=None).system_prompts_path)
    golden = json.loads((Path(__file__).resolve().parents[1] / "evals" / "golden.json").read_text())

    injection = catalog.get("injection")
    document_type = catalog.get("document_type")

    assert injection.version == 1
    assert injection.placeholders == ("chunk_text",)
    assert injection.question_type == "noul"
    assert injection.render("hello") == "hello"
    assert set(document_type.criteria or {}) == set(golden["document_types"])


def test_loader_rejects_a_placeholder_missing_from_the_template(tmp_path: Path) -> None:
    path = _file(tmp_path, _VALID.replace("placeholders: [chunk_text]", "placeholders: [other]", 1))

    with pytest.raises(ValueError, match="placeholders do not match"):
        load_system_prompts(path)


def test_loader_rejects_a_missing_version(tmp_path: Path) -> None:
    path = _file(tmp_path, _VALID.replace("  version: 1\n", "", 1))

    with pytest.raises(ValueError, match="version"):
        load_system_prompts(path)


def test_loader_rejects_a_missing_required_prompt(tmp_path: Path) -> None:
    path = _file(tmp_path, _VALID.split("- id: document_type")[0])

    with pytest.raises(ValueError, match="missing system prompts: document_type"):
        load_system_prompts(path)


def test_startup_rejects_a_bad_system_prompt_file(tmp_path: Path) -> None:
    path = _file(tmp_path, "- id: injection\n")

    with pytest.raises(ValueError, match="version"):
        create_app(Settings(_env_file=None, system_prompts_path=path))


def test_flag_threshold_must_be_a_probability() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, classifier_flag_threshold=1.5)

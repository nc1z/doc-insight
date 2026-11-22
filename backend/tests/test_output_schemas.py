import json
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.pipeline.models import (
    ConsolidatedReport,
    DocumentSummary,
    DocumentType,
)
from app.pipeline.prompts import load_system_prompts

_GOLDEN = Path(__file__).resolve().parents[1] / "evals" / "golden.json"


def test_document_types_match_the_eval_and_the_prompt() -> None:
    golden = json.loads(_GOLDEN.read_text())
    settings = Settings(_env_file=None, classifier_provider="mock")
    catalog = load_system_prompts(settings.system_prompts_path)
    names = list(get_args(DocumentType))

    assert names == golden["document_types"]
    assert list(catalog.get("document_type").criteria or {}) == names


def test_document_summary_keeps_a_point_with_its_page_and_quote() -> None:
    summary = DocumentSummary.model_validate(
        {
            "title": "Harbour Line",
            "inferred_type": "report",
            "summary": "The extension costs $420 million.",
            "key_points": ["Cost is $420 million"],
            "sections": [{"heading": "Cost", "paragraphs": ["The cost is $420 million."]}],
            "topics": ["light rail"],
            "entities": {
                "people": [{"name": "Tomás Reyes"}],
                "organisations": [{"name": "Port Arden City Council", "aliases": ["the council"]}],
            },
            "notable_points": [
                {"text": "Total cost is $420 million", "page": 1, "quote": "$420 million"}
            ],
        }
    )

    point = summary.notable_points[0]
    assert point.page == 1
    assert point.quote == "$420 million"
    assert summary.entities.organisations[0].aliases == ["the council"]


def test_a_contradiction_holds_both_claims() -> None:
    report = ConsolidatedReport.model_validate(
        {
            "summary": "The documents disagree on the cost.",
            "themes": ["cost"],
            "contradictions": [
                {
                    "about": "Project cost",
                    "claims": [
                        {
                            "text": "The cost is $420 million",
                            "document": "council-report.pdf",
                            "page": 1,
                            "quote": "$420 million",
                        },
                        {
                            "text": "The cost is $380 million",
                            "document": "contractor-release.pdf",
                            "page": 1,
                            "quote": "$380 million",
                        },
                    ],
                }
            ],
            "takeaways": ["Check the cost"],
            "sections": [{"heading": "Cost", "paragraphs": ["The cost is $420 million."]}],
            "flagged_documents": [],
            "excluded_files": [],
        }
    )

    assert len(report.contradictions[0].claims) == 2
    assert report.contradictions[0].claims[1].document == "contractor-release.pdf"


def test_one_claim_is_not_a_contradiction() -> None:
    with pytest.raises(ValidationError):
        ConsolidatedReport.model_validate(
            {
                "summary": "One figure.",
                "themes": ["cost"],
                "contradictions": [
                    {
                        "about": "Project cost",
                        "claims": [
                            {
                                "text": "The cost is $420 million",
                                "document": "council-report.pdf",
                                "page": 1,
                                "quote": "$420 million",
                            }
                        ],
                    }
                ],
                "takeaways": ["Check the cost"],
                "sections": [{"heading": "Cost", "paragraphs": ["The cost is $420 million."]}],
                "flagged_documents": [],
                "excluded_files": [],
            }
        )


def test_an_unknown_document_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DocumentSummary.model_validate(
            {
                "title": "Note",
                "inferred_type": "memo",
                "summary": "A note.",
                "key_points": ["Cost is $420 million"],
                "sections": [{"heading": "Cost", "paragraphs": ["The cost is $420 million."]}],
                "topics": [],
                "notable_points": [],
            }
        )

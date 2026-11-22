from app.pipeline.citations import supported_points
from app.pipeline.models import NotablePoint, PageText


def test_a_quote_stays_when_it_is_on_the_cited_page() -> None:
    pages = [PageText(page=1, text="The cost is $420 million today")]
    kept = supported_points(
        [
            NotablePoint(text="Cost", page=1, quote="420 million"),
            NotablePoint(text="Missing", page=1, quote="not on the page"),
            NotablePoint(text="Other page", page=2, quote="420 million"),
        ],
        pages,
    )

    assert [point.text for point in kept] == ["Cost"]


def test_a_quote_matches_across_line_breaks() -> None:
    pages = [PageText(page=1, text="The cost is\n$420 million")]
    kept = supported_points(
        [NotablePoint(text="Cost", page=1, quote="cost is $420 million")],
        pages,
    )

    assert [point.quote for point in kept] == ["cost is $420 million"]

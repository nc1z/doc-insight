from typing import Annotated, Literal

from pydantic import BaseModel, Field

DocumentType = Literal[
    "report",
    "news_article",
    "press_release",
    "letter",
    "assessment",
    "forecast",
    "survey",
    "transcript",
    "newsletter",
    "article",
    "other",
]
_Text = Annotated[str, Field(min_length=1)]
# One line a reader can take in at a glance. The cap is a guard, not a target: the prompts
# ask for far fewer words, and a longer answer is sent back to the model to shorten.
_Headline = Annotated[str, Field(min_length=1, max_length=130)]
_OneLiner = Annotated[str, Field(min_length=1, max_length=150)]
_Heading = Annotated[str, Field(min_length=1, max_length=60)]
_Tag = Annotated[str, Field(min_length=1, max_length=28)]
_Paragraph = Annotated[str, Field(min_length=1, max_length=320)]


class PageText(BaseModel):
    page: int
    text: str
    needs_image: bool = False


class PageChunk(BaseModel):
    page: int
    text: str
    token_count: int


class ExtractInput(BaseModel):
    filename: str
    page_count: int | None


class ExtractedText(BaseModel):
    pages: list[PageText]


class CheckResult(BaseModel):
    flagged: bool
    label: str
    score: float
    document_type: str
    excerpt: str = ""


class NotablePoint(BaseModel):
    text: _Text
    page: int = Field(ge=1)
    quote: _Text


class Entity(BaseModel):
    name: _Text
    aliases: list[_Text] = Field(default_factory=list)


class Entities(BaseModel):
    people: list[Entity] = Field(default_factory=list)
    organisations: list[Entity] = Field(default_factory=list)
    locations: list[Entity] = Field(default_factory=list)
    dates: list[Entity] = Field(default_factory=list)


class ChunkSummary(BaseModel):
    topics: list[_Text]
    entities: Entities = Field(default_factory=Entities)
    notable_points: list[NotablePoint]


class PullQuote(BaseModel):
    """A line copied from a document, shown between paragraphs."""

    quote: _Text
    page: int = Field(ge=1)
    document: str = ""


class Section(BaseModel):
    """One topic to read about: a short heading, short paragraphs, and optional quotes."""

    heading: _Heading
    paragraphs: list[_Paragraph] = Field(min_length=1, max_length=4)
    quotes: list[PullQuote] = Field(default_factory=list, max_length=2)


class DocumentSummary(BaseModel):
    title: _Heading = Field(description="The document's name in at most six words.")
    inferred_type: DocumentType
    summary: _Headline = Field(
        description="One sentence of at most 12 words: the single most important idea."
    )
    key_points: list[_OneLiner] = Field(
        min_length=1,
        max_length=3,
        description="Up to three one-line points, most important first.",
    )
    sections: list[Section] = Field(
        min_length=1,
        max_length=3,
        description="What to read after the key points: detail and context, not a repeat.",
    )
    topics: list[_Tag] = Field(max_length=6, description="Short tags of one or two words.")
    entities: Entities = Field(default_factory=Entities)
    notable_points: list[NotablePoint]


class Claim(BaseModel):
    text: _Text
    document: _Text
    page: int = Field(ge=1)
    quote: _Text


class Contradiction(BaseModel):
    about: _Text
    claims: list[Claim] = Field(min_length=2, max_length=2)


class ConsolidatedReport(BaseModel):
    summary: _Headline = Field(
        description="One sentence of at most 12 words: the most important idea across the documents."
    )
    themes: list[_Tag] = Field(max_length=6, description="Short tags of one or two words.")
    contradictions: list[Contradiction] = Field(default_factory=list)
    entities: Entities = Field(default_factory=Entities)
    takeaways: list[_OneLiner] = Field(
        min_length=1,
        max_length=5,
        description="Up to five one-line points that read in order, like a short story.",
    )
    sections: list[Section] = Field(
        min_length=1,
        max_length=5,
        description="Further reading, one section per theme. Disagreements go in contradictions.",
    )
    flagged_documents: list[str]
    excluded_files: list[str]

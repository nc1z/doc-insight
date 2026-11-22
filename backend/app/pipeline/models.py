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


class DocumentSummary(BaseModel):
    title: _Text
    inferred_type: DocumentType
    summary: _Text
    topics: list[_Text]
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
    summary: _Text
    themes: list[_Text]
    contradictions: list[Contradiction] = Field(default_factory=list)
    entities: Entities = Field(default_factory=Entities)
    takeaways: list[_Text]
    flagged_documents: list[str]
    excluded_files: list[str]

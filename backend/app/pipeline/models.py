from pydantic import BaseModel, Field


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
    text: str
    page: int
    quote: str


class DocumentSummary(BaseModel):
    title: str
    inferred_type: str
    summary: str
    topics: list[str]
    entities: list[str]
    notable_points: list[NotablePoint]


class ConsolidatedReport(BaseModel):
    summary: str
    themes: list[str]
    contradictions: list[str] = Field(default_factory=list)
    entities: list[str]
    takeaways: list[str]
    flagged_documents: list[str]
    excluded_files: list[str]

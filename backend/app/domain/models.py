from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, false, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain.status import DocumentStatus, JobStatus


class Base(DeclarativeBase):
    pass


def _status_type(enum: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    status: Mapped[JobStatus] = mapped_column(_status_type(JobStatus, "job_status"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    documents: Mapped[list[Document]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        _status_type(DocumentStatus, "document_status"),
        default=DocumentStatus.PENDING,
    )
    filename: Mapped[str] = mapped_column(String(1024))
    storage_key: Mapped[str | None] = mapped_column(String(1024), unique=True)
    sha256: Mapped[str | None] = mapped_column(String(64))
    page_count: Mapped[int | None]
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    excluded: Mapped[bool] = mapped_column(server_default=false(), default=False)
    flagged: Mapped[bool] = mapped_column(server_default=false(), default=False)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    job: Mapped[Job] = relationship(back_populates="documents")
    pages: Mapped[list[Page]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="Page.page_number",
    )
    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="Chunk.position",
    )
    guardrails: Mapped[list[GuardrailResult]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="GuardrailResult.page_number",
    )


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("document_id", "page_number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
    )
    page_number: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    needs_image: Mapped[bool] = mapped_column(server_default=false(), default=False)

    document: Mapped[Document] = relationship(back_populates="pages")


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("document_id", "position"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
    )
    page_number: Mapped[int]
    position: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int]

    document: Mapped[Document] = relationship(back_populates="chunks")


class LlmCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        index=True,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
    )
    model: Mapped[str] = mapped_column(String(128))
    prompt_id: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[int]
    input_tokens: Mapped[int]
    output_tokens: Mapped[int]
    latency_ms: Mapped[int]
    position: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class GuardrailResult(Base):
    __tablename__ = "guardrail_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
    )
    page_number: Mapped[int]
    rule: Mapped[str] = mapped_column(String(64))
    excerpt: Mapped[str] = mapped_column(Text)

    document: Mapped[Document] = relationship(back_populates="guardrails")

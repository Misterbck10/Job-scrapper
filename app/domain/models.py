import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

CRAWL_STATUSES = ("queued", "completed")


class Base(DeclarativeBase):
    pass


class Country(Base):
    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country_code: Mapped[str | None] = mapped_column(
        String(2), ForeignKey("countries.code"), nullable=True
    )


class Search(Base):
    __tablename__ = "searches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    query: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    country_code: Mapped[str | None] = mapped_column(
        String(2), ForeignKey("countries.code"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    crawl_runs: Mapped[list["CrawlRun"]] = relationship(back_populates="search")


class CrawlRun(Base):
    __tablename__ = "crawl_runs"
    __table_args__ = (
        UniqueConstraint("search_id", "idempotency_key", name="uq_crawl_runs_search_idempotency"),
        CheckConstraint(f"status IN {CRAWL_STATUSES}", name="ck_crawl_runs_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("searches.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    search: Mapped["Search"] = relationship(back_populates="crawl_runs")
    crawl_jobs: Mapped[list["CrawlJob"]] = relationship(back_populates="crawl_run")


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"
    __table_args__ = (CheckConstraint(f"status IN {CRAWL_STATUSES}", name="ck_crawl_jobs_status"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crawl_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crawl_runs.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    crawl_run: Mapped["CrawlRun"] = relationship(back_populates="crawl_jobs")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="crawl_job")


class JobPost(Base):
    __tablename__ = "job_posts"
    __table_args__ = (Index("ix_job_posts_created_at_id", "created_at", "id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    company: Mapped[str] = mapped_column(String(300), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crawl_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crawl_jobs.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    crawl_job: Mapped["CrawlJob"] = relationship(back_populates="artifacts")

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.cursor import decode_cursor, encode_cursor
from app.db.session import get_session
from app.domain.models import JobPost

router = APIRouter()


class JobPostOut(BaseModel):
    id: UUID
    source_id: UUID | None
    title: str
    company: str
    canonical_url: str
    created_at: datetime

    model_config = {"from_attributes": True}


class JobPostPage(BaseModel):
    items: list[JobPostOut]
    next_cursor: str | None = None


@router.get("/jobs", response_model=JobPostPage)
async def list_jobs(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> JobPostPage:
    stmt = select(JobPost).order_by(JobPost.created_at, JobPost.id).limit(limit + 1)

    if cursor is not None:
        cursor_created_at, cursor_id = decode_cursor(cursor)
        stmt = stmt.where(tuple_(JobPost.created_at, JobPost.id) > (cursor_created_at, cursor_id))

    rows = (await session.execute(stmt)).scalars().all()

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = encode_cursor(last.created_at, last.id)

    return JobPostPage(
        items=[JobPostOut.model_validate(row) for row in rows], next_cursor=next_cursor
    )

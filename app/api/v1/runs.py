from datetime import datetime
from uuid import UUID

from arq import ArqRedis
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.queue import get_arq_pool
from app.db.session import get_session
from app.domain.models import CrawlJob, CrawlRun, Search

router = APIRouter()


class RunCreateOut(BaseModel):
    crawl_run_id: UUID


class RunOut(BaseModel):
    id: UUID
    search_id: UUID
    status: str
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


@router.post("/searches/{search_id}/runs", status_code=202, response_model=RunCreateOut)
async def create_run(
    search_id: UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> RunCreateOut:
    search = await session.get(Search, search_id)
    if search is None:
        raise HTTPException(status_code=404, detail="Search not found")

    if idempotency_key is not None:
        existing = (
            await session.execute(
                select(CrawlRun).where(CrawlRun.idempotency_key == idempotency_key)
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.search_id != search_id:
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency-Key already used for a different search_id",
                )
            return RunCreateOut(crawl_run_id=existing.id)

    crawl_run = CrawlRun(search_id=search_id, status="queued", idempotency_key=idempotency_key)
    session.add(crawl_run)
    await session.flush()

    crawl_job = CrawlJob(crawl_run_id=crawl_run.id, status="queued")
    session.add(crawl_job)
    await session.commit()

    await arq_pool.enqueue_job("complete_crawl_run", str(crawl_run.id))

    return RunCreateOut(crawl_run_id=crawl_run.id)


@router.get("/runs/{crawl_run_id}", response_model=RunOut)
async def get_run(crawl_run_id: UUID, session: AsyncSession = Depends(get_session)) -> CrawlRun:
    crawl_run = await session.get(CrawlRun, crawl_run_id)
    if crawl_run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return crawl_run

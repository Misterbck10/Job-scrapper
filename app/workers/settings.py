from datetime import UTC, datetime
from typing import Any

from arq.connections import RedisSettings
from sqlalchemy import select

from app.core.config import get_settings
from app.db import session as session_module
from app.domain.models import CrawlJob, CrawlRun


async def complete_crawl_run(ctx: dict[str, Any], crawl_run_id: str) -> None:
    async with session_module._session_factory() as session:
        crawl_run = await session.get(CrawlRun, crawl_run_id)
        if crawl_run is None:
            return

        now = datetime.now(UTC)
        crawl_run.status = "completed"
        crawl_run.completed_at = now

        crawl_job = (
            await session.execute(select(CrawlJob).where(CrawlJob.crawl_run_id == crawl_run_id))
        ).scalar_one_or_none()
        if crawl_job is not None:
            crawl_job.status = "completed"

        await session.commit()


class WorkerSettings:
    functions = [complete_crawl_run]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)

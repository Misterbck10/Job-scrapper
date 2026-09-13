from httpx import AsyncClient
from sqlalchemy import insert

from app.db import session as session_module
from app.domain.models import JobPost


async def _seed_job_posts(count: int) -> None:
    async with session_module._session_factory() as session:
        await session.execute(
            insert(JobPost),
            [
                {
                    "title": f"Job {i}",
                    "company": "Acme",
                    "canonical_url": f"https://example.com/{i}",
                }
                for i in range(count)
            ],
        )
        await session.commit()


async def test_jobs_pagination_covers_all_items_without_duplicates(
    app_client: AsyncClient,
) -> None:
    await _seed_job_posts(9)

    seen_ids: set[str] = set()
    cursor = None

    for _ in range(20):
        params = {"limit": 4}
        if cursor is not None:
            params["cursor"] = cursor

        resp = await app_client.get("/v1/jobs", params=params)
        assert resp.status_code == 200
        body = resp.json()

        for item in body["items"]:
            assert item["id"] not in seen_ids
            seen_ids.add(item["id"])

        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert len(seen_ids) == 9


async def test_jobs_invalid_cursor_returns_422(app_client: AsyncClient) -> None:
    resp = await app_client.get("/v1/jobs", params={"cursor": "not-valid!!"})
    assert resp.status_code == 422

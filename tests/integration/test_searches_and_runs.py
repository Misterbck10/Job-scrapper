from httpx import AsyncClient

from app.workers.settings import complete_crawl_run


async def test_happy_path_create_search_run_and_worker_completes_it(
    app_client: AsyncClient,
) -> None:
    search_resp = await app_client.post(
        "/v1/searches", json={"name": "test", "query": {}, "country_code": "AT"}
    )
    assert search_resp.status_code == 201
    search_id = search_resp.json()["id"]

    run_resp = await app_client.post(f"/v1/searches/{search_id}/runs")
    assert run_resp.status_code == 202
    crawl_run_id = run_resp.json()["crawl_run_id"]

    await complete_crawl_run({}, crawl_run_id)

    status_resp = await app_client.get(f"/v1/runs/{crawl_run_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "completed"
    assert status_resp.json()["completed_at"] is not None


async def test_run_creation_404_for_missing_search(app_client: AsyncClient) -> None:
    resp = await app_client.post("/v1/searches/00000000-0000-0000-0000-000000000000/runs")
    assert resp.status_code == 404


async def test_idempotency_replay_returns_same_run(app_client: AsyncClient) -> None:
    search_resp = await app_client.post("/v1/searches", json={"name": "idem", "query": {}})
    search_id = search_resp.json()["id"]

    first = await app_client.post(
        f"/v1/searches/{search_id}/runs", headers={"Idempotency-Key": "key-1"}
    )
    second = await app_client.post(
        f"/v1/searches/{search_id}/runs", headers={"Idempotency-Key": "key-1"}
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["crawl_run_id"] == second.json()["crawl_run_id"]


async def test_idempotency_key_conflict_across_searches(app_client: AsyncClient) -> None:
    search_a = (await app_client.post("/v1/searches", json={"name": "a", "query": {}})).json()["id"]
    search_b = (await app_client.post("/v1/searches", json={"name": "b", "query": {}})).json()["id"]

    first = await app_client.post(
        f"/v1/searches/{search_a}/runs", headers={"Idempotency-Key": "shared-key"}
    )
    assert first.status_code == 202

    conflict = await app_client.post(
        f"/v1/searches/{search_b}/runs", headers={"Idempotency-Key": "shared-key"}
    )
    assert conflict.status_code == 409


async def test_get_run_404_when_missing(app_client: AsyncClient) -> None:
    resp = await app_client.get("/v1/runs/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404

from httpx import AsyncClient


async def test_healthz_returns_ok(app_client: AsyncClient) -> None:
    resp = await app_client.get("/healthz")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_readyz_reports_degraded_when_artifact_store_unreachable(
    app_client: AsyncClient,
) -> None:
    # conftest points S3_ENDPOINT_URL at a host nothing is listening on, so the
    # DB/ARQ checks succeed but the artifact store connectivity check must fail.
    resp = await app_client.get("/readyz")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert "artifact store" in body["reason"]


async def test_healthz_response_carries_request_id_header(app_client: AsyncClient) -> None:
    resp = await app_client.get("/healthz", headers={"X-Request-ID": "integration-trace-1"})

    assert resp.headers["X-Request-ID"] == "integration-trace-1"

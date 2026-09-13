import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging import REQUEST_ID_HEADER, request_id_middleware


def _make_app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(request_id_middleware)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_generates_request_id_when_absent() -> None:
    client = TestClient(_make_app())

    response = client.get("/ping")

    assert response.status_code == 200
    assert REQUEST_ID_HEADER in response.headers
    assert len(response.headers[REQUEST_ID_HEADER]) > 0


def test_propagates_client_supplied_request_id() -> None:
    client = TestClient(_make_app())

    response = client.get("/ping", headers={REQUEST_ID_HEADER: "client-trace-123"})

    assert response.headers[REQUEST_ID_HEADER] == "client-trace-123"


def test_binds_request_id_to_structlog_context() -> None:
    app = FastAPI()
    app.middleware("http")(request_id_middleware)
    seen_context: dict[str, object] = {}

    @app.get("/ping")
    def ping() -> dict[str, str]:
        seen_context.update(structlog.contextvars.get_contextvars())
        return {"status": "ok"}

    client = TestClient(app)
    client.get("/ping", headers={REQUEST_ID_HEADER: "trace-abc"})

    assert seen_context.get("request_id") == "trace-abc"


def test_each_request_gets_a_distinct_generated_id() -> None:
    client = TestClient(_make_app())

    first = client.get("/ping").headers[REQUEST_ID_HEADER]
    second = client.get("/ping").headers[REQUEST_ID_HEADER]

    assert first != second

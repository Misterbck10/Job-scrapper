from app.domain.models import Base


def test_crawl_run_has_idempotency_unique_constraint() -> None:
    table = Base.metadata.tables["crawl_runs"]
    constraint_names = {c.name for c in table.constraints}

    assert "uq_crawl_runs_search_idempotency" in constraint_names


def test_crawl_run_status_column_default_is_queued() -> None:
    # SQLAlchemy's column default applies on INSERT, not on object construction,
    # so the constraint we can assert here is the declared default itself.
    table = Base.metadata.tables["crawl_runs"]
    default = table.columns["status"].default
    assert default is not None
    assert default.arg == "queued"  # type: ignore[union-attr]

from app.domain.models import Base


def test_all_seven_tables_are_registered() -> None:
    expected = {
        "countries",
        "sources",
        "searches",
        "crawl_runs",
        "crawl_jobs",
        "job_posts",
        "artifacts",
    }
    assert expected == set(Base.metadata.tables.keys())


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


def test_crawl_run_status_check_constraint_restricts_values() -> None:
    table = Base.metadata.tables["crawl_runs"]
    check_names = {c.name for c in table.constraints if hasattr(c, "sqltext")}
    assert "ck_crawl_runs_status" in check_names


def test_crawl_job_status_check_constraint_restricts_values() -> None:
    table = Base.metadata.tables["crawl_jobs"]
    check_names = {c.name for c in table.constraints if hasattr(c, "sqltext")}
    assert "ck_crawl_jobs_status" in check_names


def test_source_source_id_is_unique() -> None:
    table = Base.metadata.tables["sources"]
    assert table.columns["source_id"].unique is True


def test_job_posts_has_keyset_pagination_index() -> None:
    table = Base.metadata.tables["job_posts"]
    index_names = {ix.name for ix in table.indexes}
    assert "ix_job_posts_created_at_id" in index_names


def test_artifact_crawl_job_id_foreign_key_targets_crawl_jobs() -> None:
    table = Base.metadata.tables["artifacts"]
    fk_targets = {fk.column.table.name for fk in table.columns["crawl_job_id"].foreign_keys}
    assert fk_targets == {"crawl_jobs"}


def test_crawl_run_search_id_foreign_key_targets_searches() -> None:
    table = Base.metadata.tables["crawl_runs"]
    fk_targets = {fk.column.table.name for fk in table.columns["search_id"].foreign_keys}
    assert fk_targets == {"searches"}

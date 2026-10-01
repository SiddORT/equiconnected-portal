"""Run the review lifecycle migration against isolated legacy PostgreSQL data."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, inspect, text

from tests.conftest import TEST_DB_URL


REVISION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "41bd7a693e20_member_feedback_history_and_review_lifecycle.py"
)
REVISION_SPEC = importlib.util.spec_from_file_location(
    "member_feedback_history_and_review_lifecycle", REVISION_PATH
)
assert REVISION_SPEC is not None and REVISION_SPEC.loader is not None
REVISION = importlib.util.module_from_spec(REVISION_SPEC)
REVISION_SPEC.loader.exec_module(REVISION)


def _schema_engine(schema: str):
    engine = create_engine(TEST_DB_URL, pool_pre_ping=True)

    @event.listens_for(engine, "connect")
    def _set_isolated_search_path(connection, _record):
        cursor = connection.cursor()
        cursor.execute(f'SET search_path TO "{schema}"')
        connection.commit()
        cursor.close()

    return engine


def test_review_migration_backfills_visibility_without_history_and_round_trips():
    schema = f"review_migration_{uuid4().hex}"
    admin_engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    admin_engine.dispose()

    engine = _schema_engine(schema)
    provider_ids = [uuid4(), uuid4()]
    member_ids = [uuid4(), uuid4()]
    review_ids = [uuid4(), uuid4()]

    try:
        with engine.begin() as connection:
            connection.execute(text(
                "CREATE TABLE users (id UUID PRIMARY KEY)"
            ))
            connection.execute(text(
                "CREATE TABLE providers (id UUID PRIMARY KEY)"
            ))
            connection.execute(text("""
                CREATE TABLE provider_reviews (
                    id UUID PRIMARY KEY,
                    provider_id UUID NOT NULL,
                    member_id UUID NOT NULL,
                    rating INTEGER NOT NULL,
                    comment TEXT NOT NULL DEFAULT '',
                    comment_visible BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    CONSTRAINT provider_reviews_provider_id_fkey
                        FOREIGN KEY (provider_id) REFERENCES providers (id)
                        ON DELETE CASCADE,
                    CONSTRAINT provider_reviews_member_id_fkey
                        FOREIGN KEY (member_id) REFERENCES users (id)
                        ON DELETE CASCADE,
                    CONSTRAINT uq_provider_reviews_provider_member
                        UNIQUE (provider_id, member_id)
                )
            """))
            connection.execute(
                text("INSERT INTO users (id) VALUES (:first), (:second)"),
                {"first": member_ids[0], "second": member_ids[1]},
            )
            connection.execute(
                text("INSERT INTO providers (id) VALUES (:first), (:second)"),
                {"first": provider_ids[0], "second": provider_ids[1]},
            )
            connection.execute(text("""
                INSERT INTO provider_reviews
                    (id, provider_id, member_id, rating, comment, comment_visible, created_at, updated_at)
                VALUES
                    (:published_id, :published_provider, :published_member, 5,
                     'Legacy approved comment', TRUE, now(), now()),
                    (:hidden_id, :hidden_provider, :hidden_member, 2,
                     'Legacy hidden comment', FALSE, now(), now())
            """), {
                "published_id": review_ids[0],
                "published_provider": provider_ids[0],
                "published_member": member_ids[0],
                "hidden_id": review_ids[1],
                "hidden_provider": provider_ids[1],
                "hidden_member": member_ids[1],
            })

        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                REVISION.upgrade()

        with engine.begin() as connection:
            rows = connection.execute(text("""
                SELECT id, status::text AS status, comment_visible, version, deleted_at
                FROM provider_reviews
                ORDER BY id
            """)).mappings().all()
            by_id = {row["id"]: row for row in rows}
            assert by_id[review_ids[0]]["status"] == "PUBLISHED"
            assert by_id[review_ids[0]]["comment_visible"] is True
            assert by_id[review_ids[1]]["status"] == "HIDDEN"
            assert by_id[review_ids[1]]["comment_visible"] is False
            assert all(row["version"] == 1 and row["deleted_at"] is None for row in rows)
            assert connection.scalar(text("SELECT count(*) FROM provider_review_actions")) == 0
            index_names = {
                index["name"] for index in inspect(connection).get_indexes("provider_reviews")
            }
            assert "uq_provider_reviews_active_provider_member" in index_names
            assert inspect(connection).has_table("member_feedback")
            assert inspect(connection).has_table("member_feedback_actions")
            assert inspect(connection).has_table("member_browsing_history")

        # The downgrade restores the legacy unique constraint and visibility
        # data; re-upgrading backfills the same states and never fabricates
        # member/admin moderation actions for historical records.
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                REVISION.downgrade()
        with engine.begin() as connection:
            inspector = inspect(connection)
            assert "status" not in {
                column["name"] for column in inspector.get_columns("provider_reviews")
            }
            unique_constraints = {
                constraint["name"]
                for constraint in inspector.get_unique_constraints("provider_reviews")
            }
            assert "uq_provider_reviews_provider_member" in unique_constraints
            visibility = dict(connection.execute(
                text("SELECT id, comment_visible FROM provider_reviews")
            ).all())
            assert visibility == {review_ids[0]: True, review_ids[1]: False}

        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                REVISION.upgrade()
        with engine.begin() as connection:
            states = dict(connection.execute(text(
                "SELECT id, status::text FROM provider_reviews"
            )).all())
            assert states == {
                review_ids[0]: "PUBLISHED",
                review_ids[1]: "HIDDEN",
            }
            assert connection.scalar(text("SELECT count(*) FROM provider_review_actions")) == 0
    finally:
        engine.dispose()
        admin_engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()
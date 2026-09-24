"""add language master and provider signup selections"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "9a1f2c3d4e5f"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("languages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(10), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))
    op.create_index("ix_languages_code", "languages", ["code"], unique=True)
    op.add_column("provider_registration_applications", sa.Column("postal_code", sa.String(32), nullable=True))
    op.execute("UPDATE provider_registration_applications SET postal_code = '' WHERE postal_code IS NULL")
    op.alter_column("provider_registration_applications", "postal_code", nullable=False)
    op.create_table("provider_registration_languages",
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("provider_registration_applications.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("language_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("languages.id", ondelete="RESTRICT"), primary_key=True))
    op.create_table("provider_languages",
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("providers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("language_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("languages.id", ondelete="RESTRICT"), primary_key=True))
    # Explicit stable IDs plus ON CONFLICT make bootstrap safe to replay in a
    # development database that may already contain part of the seed.
    seed = [
        ("00000000-0000-0000-0000-000000000001", "English", "en"),
        ("00000000-0000-0000-0000-000000000002", "Spanish", "es"),
        ("00000000-0000-0000-0000-000000000003", "French", "fr"),
        ("00000000-0000-0000-0000-000000000004", "German", "de"),
        ("00000000-0000-0000-0000-000000000005", "Arabic", "ar"),
        ("00000000-0000-0000-0000-000000000006", "Italian", "it"),
        ("00000000-0000-0000-0000-000000000007", "Portuguese", "pt"),
        ("00000000-0000-0000-0000-000000000008", "Chinese", "zh"),
        ("00000000-0000-0000-0000-000000000009", "Japanese", "ja"),
        ("00000000-0000-0000-0000-00000000000a", "Korean", "ko"),
        ("00000000-0000-0000-0000-00000000000b", "Russian", "ru"),
        ("00000000-0000-0000-0000-00000000000c", "Hindi", "hi"),
    ]
    values = ", ".join(
        f"('{id}', '{name.replace(chr(39), chr(39) + chr(39))}', '{code}', TRUE)"
        for id, name, code in seed
    )
    op.execute(
        "INSERT INTO languages (id, name, code, is_active) VALUES "
        + values
        + " ON CONFLICT (code) DO NOTHING"
    )

def downgrade():
    op.drop_table("provider_languages")
    op.drop_table("provider_registration_languages")
    op.drop_column("provider_registration_applications", "postal_code")
    op.drop_index("ix_languages_code", table_name="languages")
    op.drop_table("languages")
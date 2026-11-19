"""Initial asset, version, and idempotency tables."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("origin_id", sa.String(length=64), primary_key=True),
        sa.Column("creator_key", sa.String(length=64), nullable=False),
        sa.Column("root_version_id", sa.String(length=64), nullable=False),
        sa.Column("identity_mode", sa.String(length=24), nullable=False),
        sa.Column("chain_kind", sa.String(length=16), nullable=False),
        sa.Column("chain_reference", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "versions",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("origin_id", sa.String(length=64), sa.ForeignKey("assets.origin_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", sa.String(length=64), nullable=False),
        sa.Column("parent_version_id", sa.String(length=64), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("manifest_core", sa.JSON(), nullable=False),
        sa.Column("signature_envelope", sa.JSON(), nullable=False),
        sa.Column("signer_key", sa.String(length=64), nullable=False),
        sa.Column("chain_kind", sa.String(length=16), nullable=False),
        sa.Column("chain_reference", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("origin_id", "version_id", name="uq_version_origin_id"),
    )
    op.create_index("ix_versions_origin_id", "versions", ["origin_id"])
    op.create_index("ix_versions_version_id", "versions", ["version_id"])
    op.create_index("ix_versions_parent_version_id", "versions", ["parent_version_id"])
    op.create_index("ix_versions_content_hash", "versions", ["content_hash"])
    op.create_table(
        "idempotency_records",
        sa.Column("key", sa.String(length=128), primary_key=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_index("ix_versions_content_hash", table_name="versions")
    op.drop_index("ix_versions_parent_version_id", table_name="versions")
    op.drop_index("ix_versions_version_id", table_name="versions")
    op.drop_index("ix_versions_origin_id", table_name="versions")
    op.drop_table("versions")
    op.drop_table("assets")

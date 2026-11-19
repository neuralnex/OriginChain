from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Asset(Base):
    __tablename__ = "assets"

    origin_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    creator_key: Mapped[str] = mapped_column(String(64), nullable=False)
    root_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    identity_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    chain_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    chain_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    versions: Mapped[list["Version"]] = relationship(back_populates="asset", cascade="all, delete-orphan")


class Version(Base):
    __tablename__ = "versions"
    __table_args__ = (UniqueConstraint("origin_id", "version_id", name="uq_version_origin_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    origin_id: Mapped[str] = mapped_column(ForeignKey("assets.origin_id", ondelete="CASCADE"), index=True)
    version_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    parent_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_core: Mapped[dict] = mapped_column(JSON, nullable=False)
    signature_envelope: Mapped[dict] = mapped_column(JSON, nullable=False)
    signer_key: Mapped[str] = mapped_column(String(64), nullable=False)
    chain_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    chain_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    asset: Mapped[Asset] = relationship(back_populates="versions")


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

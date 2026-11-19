from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RegisterAssetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: dict[str, Any]
    signature: dict[str, str]
    content_base64: str = Field(description="Exact media bytes encoded as standard Base64; never persisted")
    transaction_base64: str | None = Field(default=None, description="Wallet-signed Solana transaction; required with CHAIN_ADAPTER=solana")


class CreateVersionRequest(RegisterAssetRequest):
    pass


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin_id: str
    version_id: str
    content_base64: str


class VersionSummary(BaseModel):
    version_id: str
    parent_version_id: str | None
    content_hash: str
    manifest_hash: str
    signer_key: str
    chain_kind: str
    chain_reference: str
    created_at: str


class AssetResponse(BaseModel):
    origin_id: str
    root_version_id: str
    identity_mode: str
    chain_kind: str
    chain_reference: str
    versions: list[VersionSummary]


class VerificationResponse(BaseModel):
    status: Literal["verified", "unverified", "tampered", "incomplete"]
    reason: str
    chain_kind: str | None = None
    origin_id: str | None = None
    version_id: str | None = None
    content_hash: str | None = None


class HealthResponse(BaseModel):
    status: str
    chain_adapter: str
    protocol_version: str = "1.0.0"

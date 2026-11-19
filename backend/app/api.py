import hashlib
from datetime import timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import Asset, IdempotencyRecord, Version
from .schemas import (
    AssetResponse,
    CreateVersionRequest,
    HealthResponse,
    RegisterAssetRequest,
    VerificationResponse,
    VerifyRequest,
    VersionSummary,
)
from .services.chain import ChainError, build_chain_adapter
from .services.protocol import RequestValidationError, decode_content, stable_request_hash, validate_submission


router = APIRouter(prefix="/v1")


def _http_error(exc: Exception, code: int = 422) -> HTTPException:
    return HTTPException(status_code=code, detail=str(exc))


def _dt(value) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _summary(version: Version) -> VersionSummary:
    return VersionSummary(
        version_id=version.version_id,
        parent_version_id=version.parent_version_id,
        content_hash=version.content_hash,
        manifest_hash=version.manifest_hash,
        signer_key=version.signer_key,
        chain_kind=version.chain_kind,
        chain_reference=version.chain_reference,
        created_at=_dt(version.created_at),
    )


def _asset_response(asset: Asset, versions: list[Version]) -> AssetResponse:
    return AssetResponse(
        origin_id=asset.origin_id,
        root_version_id=asset.root_version_id,
        identity_mode=asset.identity_mode,
        chain_kind=asset.chain_kind,
        chain_reference=asset.chain_reference,
        versions=[_summary(item) for item in versions],
    )


def _idempotent_replay(db: Session, key: str | None, request_hash: str):
    if not key:
        return None
    prior = db.get(IdempotencyRecord, key)
    if prior is None:
        return None
    if prior.request_hash != request_hash:
        raise HTTPException(status_code=409, detail="Idempotency-Key was already used for a different request")
    return prior.response_json


def _store_idempotency(db: Session, key: str | None, request_hash: str, response: dict) -> None:
    if key:
        db.add(IdempotencyRecord(key=key, request_hash=request_hash, response_json=response))


def _validate_key(key: str | None) -> None:
    if key is not None and not (1 <= len(key) <= 128):
        raise HTTPException(status_code=400, detail="Idempotency-Key must be between 1 and 128 characters")


def _submit(db: Session, payload: RegisterAssetRequest, idempotency_key: str | None, operation: str, parent: Version | None = None):
    _validate_key(idempotency_key)
    settings = get_settings()
    try:
        content = decode_content(payload.content_base64, settings.max_upload_bytes)
        parent_core = parent.manifest_core if parent else None
        digest, _ = validate_submission(payload.manifest, payload.signature, content, parent_core)
    except RequestValidationError as exc:
        raise _http_error(exc) from exc

    core = payload.manifest
    origin_id = core["origin_id"]
    version_id = core["version_id"]
    if operation == "register":
        if core["parent_version_id"] is not None:
            raise HTTPException(status_code=422, detail="asset registration requires a root manifest")
    else:
        if core["parent_version_id"] is None:
            raise HTTPException(status_code=422, detail="version creation requires a parent Version")
        if db.get(Asset, origin_id) is None:
            raise HTTPException(status_code=404, detail="Origin was not found")

    request_hash = stable_request_hash(core, payload.signature, content, payload.transaction_base64, operation)
    replay = _idempotent_replay(db, idempotency_key, request_hash)
    if replay is not None:
        return replay

    if operation == "register":
        if db.get(Asset, origin_id) is not None:
            raise HTTPException(status_code=409, detail="Origin ID is already registered")
    elif db.scalar(select(Version).where(Version.origin_id == origin_id, Version.version_id == version_id)):
        raise HTTPException(status_code=409, detail="Version ID is already registered")

    try:
        adapter = build_chain_adapter(settings)
        chain_reference = adapter.commit(
            operation=operation,
            core=core,
            signer=payload.signature["public_key"],
            transaction_base64=payload.transaction_base64,
        )
    except ChainError as exc:
        raise _http_error(exc, 502) from exc
    except ValueError as exc:
        raise _http_error(exc, 500) from exc

    chain_kind = adapter.kind
    if operation == "register":
        asset = Asset(
            origin_id=origin_id,
            creator_key=payload.signature["public_key"],
            root_version_id=version_id,
            identity_mode=core["identity_mode"],
            chain_kind=chain_kind,
            chain_reference=chain_reference,
        )
        db.add(asset)
    else:
        asset = db.get(Asset, origin_id)
        if asset.chain_kind != chain_kind:
            raise HTTPException(status_code=409, detail="asset and version use different chain adapters")

    version = Version(
        origin_id=origin_id,
        version_id=version_id,
        parent_version_id=core["parent_version_id"],
        content_hash=core["content_hash"],
        manifest_hash=digest,
        manifest_core=core,
        signature_envelope=payload.signature,
        signer_key=payload.signature["public_key"],
        chain_kind=chain_kind,
        chain_reference=chain_reference,
    )
    db.add(version)
    db.flush()
    if operation == "register":
        response = _asset_response(asset, [version]).model_dump(mode="json")
    else:
        response = _summary(version).model_dump(mode="json")
    _store_idempotency(db, idempotency_key, request_hash, response)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if idempotency_key:
            replay = _idempotent_replay(db, idempotency_key, request_hash)
            if replay is not None:
                return replay
        raise HTTPException(status_code=409, detail="asset or version was concurrently registered") from exc
    return response


@router.get("/health", response_model=HealthResponse)
def health():
    settings = get_settings()
    return HealthResponse(status="ok", chain_adapter=settings.chain_adapter.lower())


@router.post("/assets", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def register_asset(
    payload: RegisterAssetRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    return _submit(db, payload, idempotency_key, "register")


@router.get("/assets/{origin_id}", response_model=AssetResponse)
def get_asset(origin_id: str, db: Session = Depends(get_db)):
    asset = db.get(Asset, origin_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Origin was not found")
    versions = list(db.scalars(select(Version).where(Version.origin_id == origin_id).order_by(Version.created_at, Version.id)))
    return _asset_response(asset, versions)


@router.get("/assets/{origin_id}/history", response_model=list[VersionSummary])
def get_history(origin_id: str, db: Session = Depends(get_db)):
    if db.get(Asset, origin_id) is None:
        raise HTTPException(status_code=404, detail="Origin was not found")
    versions = db.scalars(select(Version).where(Version.origin_id == origin_id).order_by(Version.created_at, Version.id))
    return [_summary(version) for version in versions]


@router.get("/assets/{origin_id}/versions", response_model=list[VersionSummary])
def get_versions(origin_id: str, db: Session = Depends(get_db)):
    return get_history(origin_id, db)


@router.get("/versions/{version_id}")
def get_version(version_id: str, origin_id: str, db: Session = Depends(get_db)):
    version = db.scalar(select(Version).where(Version.origin_id == origin_id, Version.version_id == version_id))
    if version is None:
        raise HTTPException(status_code=404, detail="Version was not found")
    return {**_summary(version).model_dump(mode="json"), "manifest": version.manifest_core, "signature": version.signature_envelope}


@router.get("/versions/{version_id}/manifest")
def get_manifest(version_id: str, origin_id: str, db: Session = Depends(get_db)):
    version = db.scalar(select(Version).where(Version.origin_id == origin_id, Version.version_id == version_id))
    if version is None:
        raise HTTPException(status_code=404, detail="Version was not found")
    return {"manifest": version.manifest_core, "signature": version.signature_envelope, "manifest_hash": version.manifest_hash}


@router.post("/assets/{origin_id}/versions", response_model=VersionSummary, status_code=status.HTTP_201_CREATED)
def create_version(
    origin_id: str,
    payload: CreateVersionRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    if payload.manifest.get("origin_id") != origin_id:
        raise HTTPException(status_code=422, detail="path Origin ID must match the manifest")
    parent_id = payload.manifest.get("parent_version_id")
    parent = db.scalar(select(Version).where(Version.origin_id == origin_id, Version.version_id == parent_id))
    if parent is None:
        raise HTTPException(status_code=422, detail="parent Version was not found for this Origin")
    return _submit(db, payload, idempotency_key, "version", parent)


@router.post("/verify", response_model=VerificationResponse)
def verify_content(payload: VerifyRequest, db: Session = Depends(get_db)):
    try:
        content = decode_content(payload.content_base64, get_settings().max_upload_bytes)
    except RequestValidationError as exc:
        raise _http_error(exc) from exc
    version = db.scalar(select(Version).where(Version.origin_id == payload.origin_id, Version.version_id == payload.version_id))
    if version is None:
        return VerificationResponse(status="unverified", reason="No matching registered Version was found.", origin_id=payload.origin_id, version_id=payload.version_id)
    from originchain_core.crypto import content_hash_bytes
    observed_hash = content_hash_bytes(content)
    if observed_hash != version.content_hash:
        return VerificationResponse(status="tampered", reason="File bytes do not match the Version commitment.", chain_kind=version.chain_kind, origin_id=payload.origin_id, version_id=payload.version_id, content_hash=observed_hash)
    try:
        parent_core = None
        if version.parent_version_id is not None:
            parent = db.scalar(select(Version).where(Version.origin_id == version.origin_id, Version.version_id == version.parent_version_id))
            if parent is None:
                raise RequestValidationError("registered parent Version is unavailable")
            parent_core = parent.manifest_core
        valid_signature = validate_submission(version.manifest_core, version.signature_envelope, content, parent_core)[0] == version.manifest_hash
    except RequestValidationError:
        valid_signature = False
    if not valid_signature:
        return VerificationResponse(status="tampered", reason="Stored manifest or signature is invalid.", chain_kind=version.chain_kind, origin_id=payload.origin_id, version_id=payload.version_id, content_hash=observed_hash)
    if version.chain_kind == "mock":
        return VerificationResponse(status="incomplete", reason="File and signature match the local mock record; no Solana commitment was verified.", chain_kind="mock", origin_id=payload.origin_id, version_id=payload.version_id, content_hash=observed_hash)
    try:
        adapter = build_chain_adapter(get_settings())
        if adapter.kind != version.chain_kind:
            return VerificationResponse(status="incomplete", reason="Configured chain adapter does not match the stored record.", chain_kind=version.chain_kind, origin_id=payload.origin_id, version_id=payload.version_id, content_hash=observed_hash)
        result = adapter.check(core=version.manifest_core, expected_manifest_hash=version.manifest_hash, expected_signer=version.signer_key, reference=version.chain_reference)
    except ChainError:
        result = None
    if result is True:
        return VerificationResponse(status="verified", reason="File hash, manifest signature, signer, and Solana account commitment agree.", chain_kind="solana", origin_id=payload.origin_id, version_id=payload.version_id, content_hash=observed_hash)
    if result is False:
        return VerificationResponse(status="tampered", reason="The Solana Version account conflicts with the registered manifest.", chain_kind="solana", origin_id=payload.origin_id, version_id=payload.version_id, content_hash=observed_hash)
    return VerificationResponse(status="incomplete", reason="File and signature match, but Solana commitment data is unavailable.", chain_kind=version.chain_kind, origin_id=payload.origin_id, version_id=payload.version_id, content_hash=observed_hash)

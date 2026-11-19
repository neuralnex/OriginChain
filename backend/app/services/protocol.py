import base64
import binascii
import hashlib
import json

from originchain_core.crypto import content_hash_bytes
from originchain_core.identifiers import decode_id
from originchain_core.manifest import ManifestError, manifest_hash, validate_manifest_core, verify_manifest_signature


class RequestValidationError(ValueError):
    pass


def decode_content(encoded: str, limit: int) -> bytes:
    if not isinstance(encoded, str):
        raise RequestValidationError("content_base64 must be a Base64 string")
    # Bound allocation before decoding; Base64 expands input by at most 4/3.
    if len(encoded) > ((limit + 2) // 3) * 4 + 4:
        raise RequestValidationError("content exceeds configured upload limit")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RequestValidationError("content_base64 is not valid standard Base64") from exc
    if len(content) > limit:
        raise RequestValidationError("content exceeds configured upload limit")
    return content


def validate_submission(core: dict, envelope: dict, content: bytes, parent_core: dict | None = None) -> tuple[str, str]:
    try:
        validate_manifest_core(core, parent_core=parent_core)
        if not verify_manifest_signature(core, envelope):
            raise RequestValidationError("manifest signature is invalid")
        digest = content_hash_bytes(content)
        if digest != core["content_hash"]:
            raise RequestValidationError("content bytes do not match manifest content_hash")
        if len(content) != core["size_bytes"]:
            raise RequestValidationError("content byte length does not match manifest size_bytes")
        if not (core["media_type"].startswith("image/") or core["media_type"].startswith("video/")):
            raise RequestValidationError("MVP accepts image/* and video/* media types")
        signer = envelope.get("public_key")
        signer_bytes = decode_id(signer)
        return manifest_hash(core), hashlib.sha256(signer_bytes).hexdigest()
    except ManifestError as exc:
        raise RequestValidationError(str(exc)) from exc
    except (TypeError, ValueError, KeyError) as exc:
        if isinstance(exc, RequestValidationError):
            raise
        raise RequestValidationError(str(exc)) from exc


def stable_request_hash(manifest: dict, signature: dict, content: bytes, transaction_base64: str | None, operation: str) -> str:
    digest = hashlib.sha256()
    digest.update(b"ORIGINCHAIN:API-REQUEST:V1\0")
    digest.update(operation.encode("ascii") + b"\0")
    digest.update(json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())
    digest.update(json.dumps(signature, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())
    digest.update(hashlib.sha256(content).digest())
    if transaction_base64:
        digest.update(hashlib.sha256(transaction_base64.encode()).digest())
    return digest.hexdigest()

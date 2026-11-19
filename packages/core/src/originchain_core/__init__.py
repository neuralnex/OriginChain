"""OriginChain protocol v1 reference implementation."""

from .crypto import content_hash_bytes, content_hash_stream
from .identifiers import decode_id, encode_id, new_id, validate_id
from .manifest import (
    ManifestError,
    canonical_json,
    manifest_hash,
    parse_manifest_json,
    sign_manifest,
    validate_manifest_core,
    verify_manifest_signature,
)

__all__ = [
    "ManifestError",
    "canonical_json",
    "content_hash_bytes",
    "content_hash_stream",
    "decode_id",
    "encode_id",
    "manifest_hash",
    "new_id",
    "parse_manifest_json",
    "sign_manifest",
    "validate_id",
    "validate_manifest_core",
    "verify_manifest_signature",
]

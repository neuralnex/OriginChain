"""Canonical manifest hashing, signing, parsing, and v1 relationship validation."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .identifiers import decode_id, encode_id

MANIFEST_DOMAIN = b"ORIGINCHAIN:MANIFEST:V1\0"
SIGNATURE_DOMAIN = b"ORIGINCHAIN:MANIFEST-SIGNATURE:V1\0"
MAX_SAFE_INTEGER = 9_007_199_254_740_991
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_MEDIA_TYPE_RE = re.compile(r"^[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+$")
_TIME_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,9})?Z$"
)
_REQUIRED = {
    "protocol", "protocol_version", "origin_id", "version_id", "manifest_id",
    "parent_version_id", "content_hash", "hash_algorithm", "media_type", "size_bytes",
    "actor", "identity_mode", "action_type", "relationship", "created_at",
}
_OPTIONAL = {"parent_manifest_hash", "sources", "application_claim"}


class ManifestError(ValueError):
    """A manifest is not valid under the protocol v1 contract."""


def _validate_json_value(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, (bool, str)):
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise ManifestError(f"{path} contains an unpaired Unicode surrogate") from exc
        return
    if isinstance(value, int):
        if value < 0 or value > MAX_SAFE_INTEGER:
            raise ManifestError(f"{path} must be a non-negative safe integer")
        return
    if isinstance(value, float):
        raise ManifestError(f"{path} must not contain floating-point numbers")
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ManifestError(f"{path} contains a non-string object key")
            _validate_json_value(key, f"{path}.<key>")
            _validate_json_value(item, f"{path}.{key}")
        return
    raise ManifestError(f"{path} contains an unsupported JSON value")


def _jcs_key(key: str) -> bytes:
    try:
        return key.encode("utf-16be")
    except UnicodeEncodeError as exc:
        raise ManifestError("object keys must not contain unpaired Unicode surrogates") from exc


def _canonical(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ",".join(_canonical(item) for item in value) + "]"
    if isinstance(value, dict):
        parts = (
            json.dumps(key, ensure_ascii=False) + ":" + _canonical(value[key])
            for key in sorted(value, key=_jcs_key)
        )
        return "{" + ",".join(parts) + "}"
    raise ManifestError(f"unsupported JSON type: {type(value).__name__}")


def canonical_json(value: Mapping[str, Any]) -> bytes:
    """Serialize the v1 JSON subset as RFC 8785 canonical UTF-8 bytes."""
    if not isinstance(value, dict):
        raise ManifestError("manifest core must be a JSON object")
    _validate_json_value(value)
    return _canonical(value).encode("utf-8")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def parse_manifest_json(raw: str | bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(raw, object_pairs_hook=_reject_duplicate_pairs)
    except ManifestError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ManifestError("manifest is not valid UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise ManifestError("manifest core must be a JSON object")
    validate_manifest_core(parsed)
    return parsed


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ManifestError(message)


def validate_manifest_core(
    core: Mapping[str, Any], parent_core: Mapping[str, Any] | None = None
) -> None:
    if not isinstance(core, dict):
        raise ManifestError("manifest core must be an object")
    _validate_json_value(core)
    keys = set(core)
    _require(_REQUIRED <= keys, f"missing manifest fields: {sorted(_REQUIRED - keys)}")
    _require(keys <= _REQUIRED | _OPTIONAL, f"unknown manifest fields: {sorted(keys - _REQUIRED - _OPTIONAL)}")
    _require(core["protocol"] == "originchain", "unsupported protocol")
    _require(core["protocol_version"] == "1.0.0", "unsupported protocol version")
    for field in ("origin_id", "version_id", "manifest_id"):
        try:
            decode_id(core[field])
        except (TypeError, ValueError) as exc:
            raise ManifestError(f"invalid {field}") from exc
    parent_id = core["parent_version_id"]
    if parent_id is not None:
        try:
            decode_id(parent_id)
        except (TypeError, ValueError) as exc:
            raise ManifestError("invalid parent_version_id") from exc
    _require(isinstance(core["content_hash"], str) and bool(_HASH_RE.fullmatch(core["content_hash"])), "content_hash must be lowercase SHA-256 hex")
    _require(core["hash_algorithm"] == "sha-256", "unsupported content hash algorithm")
    _require(isinstance(core["media_type"], str) and bool(_MEDIA_TYPE_RE.fullmatch(core["media_type"])), "media_type must be a lowercase type/subtype")
    _require(type(core["size_bytes"]) is int and 0 <= core["size_bytes"] <= MAX_SAFE_INTEGER, "invalid size_bytes")

    actor = core["actor"]
    _require(isinstance(actor, dict) and set(actor) == {"actor_id", "actor_type"}, "actor must contain actor_id and actor_type only")
    try:
        decode_id(actor["actor_id"])
    except (TypeError, ValueError) as exc:
        raise ManifestError("invalid actor_id") from exc
    _require(isinstance(actor["actor_type"], str) and actor["actor_type"] in {"person", "application", "device", "organization", "unknown"}, "invalid actor_type")
    _require(isinstance(core["identity_mode"], str) and core["identity_mode"] in {"anonymous", "pseudonymous", "credentialed"}, "invalid identity_mode")
    _require(isinstance(core["action_type"], str) and core["action_type"] in {"create", "edit", "ai_modify", "transform", "compose"}, "invalid action_type")
    _require(isinstance(core["relationship"], str) and core["relationship"] in {"root", "continuation", "derivative", "composition"}, "invalid relationship")
    timestamp = core["created_at"]
    _require(isinstance(timestamp, str) and bool(_TIME_RE.fullmatch(timestamp)), "created_at must be an RFC 3339 UTC timestamp")
    try:
        datetime.fromisoformat(timestamp[:-1] + "+00:00")
    except ValueError as exc:
        raise ManifestError("created_at is not a valid calendar timestamp") from exc

    parent_hash = core.get("parent_manifest_hash")
    _require(parent_hash is None or (isinstance(parent_hash, str) and bool(_HASH_RE.fullmatch(parent_hash))), "invalid parent_manifest_hash")
    sources = core.get("sources", [])
    _require(isinstance(sources, list), "sources must be an array")
    for source in sources:
        _require(isinstance(source, dict) and set(source) == {"origin_id", "version_id", "role"}, "invalid source reference")
        try:
            decode_id(source["origin_id"])
            decode_id(source["version_id"])
        except (TypeError, ValueError) as exc:
            raise ManifestError("invalid source ID") from exc
        _require(isinstance(source["role"], str) and 1 <= len(source["role"]) <= 64, "invalid source role")

    application = core.get("application_claim")
    if application is not None:
        _require(isinstance(application, dict), "application_claim must be an object")
        _require(set(application) <= {"application_id", "application_version", "model_id", "model_version"}, "unknown application_claim field")
        _require({"application_id", "application_version"} <= set(application), "application_claim is missing required fields")
        _require(all(isinstance(application[field], str) and 1 <= len(application[field]) <= 256 for field in application), "invalid application_claim value")

    relationship = core["relationship"]
    if parent_id is None:
        _require(parent_hash is None, "root manifest must not have a parent manifest hash")
        if relationship == "root":
            _require(core["action_type"] == "create" and not sources, "independent root must be a source-free create")
        elif relationship == "derivative":
            _require(len(sources) >= 1, "root derivative must cite at least one source")
        else:
            _require(len(sources) >= 2, "root composition must cite at least two sources")
    else:
        _require(parent_hash is not None, "non-root manifest must include parent_manifest_hash")
        _require(relationship in {"continuation", "composition"}, "child version must be a continuation or composition")
        if parent_core is not None:
            validate_manifest_core(parent_core)
            _require(parent_core["origin_id"] == core["origin_id"], "parent must belong to the same Origin")
            _require(parent_core["version_id"] == parent_id, "parent_version_id does not match the supplied parent")
            _require(manifest_hash(parent_core) == parent_hash, "parent manifest hash does not match the supplied parent")
            _require(parent_core["content_hash"] != core["content_hash"], "new Version must have different content bytes")


def manifest_hash(core: Mapping[str, Any]) -> str:
    validate_manifest_core(core)
    import hashlib

    return hashlib.sha256(MANIFEST_DOMAIN + canonical_json(core)).hexdigest()


def _private_key(key: bytes | Ed25519PrivateKey) -> Ed25519PrivateKey:
    if isinstance(key, Ed25519PrivateKey):
        return key
    if not isinstance(key, bytes) or len(key) != 32:
        raise ManifestError("Ed25519 private key must be a 32-byte seed")
    return Ed25519PrivateKey.from_private_bytes(key)


def sign_manifest(core: Mapping[str, Any], private_key: bytes | Ed25519PrivateKey) -> dict[str, str]:
    digest = bytes.fromhex(manifest_hash(core))
    signer = _private_key(private_key)
    public_key = signer.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    signature = signer.sign(SIGNATURE_DOMAIN + digest)
    return {"algorithm": "Ed25519", "public_key": encode_id(public_key), "signature": _base58(signature)}


def _base58(raw: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = int.from_bytes(raw, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = alphabet[remainder] + encoded
    leading_zeroes = len(raw) - len(raw.lstrip(b"\0"))
    return "1" * leading_zeroes + encoded


def _decode_base58_bytes(value: str) -> bytes:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    digits = {character: index for index, character in enumerate(alphabet)}
    number = 0
    try:
        for character in value:
            number = number * 58 + digits[character]
    except (KeyError, TypeError) as exc:
        raise ManifestError("invalid base58 value") from exc
    body = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return b"\0" * (len(value) - len(value.lstrip("1"))) + body


def verify_manifest_signature(
    core: Mapping[str, Any],
    envelope: Mapping[str, str],
    authorized_public_keys: set[str] | None = None,
) -> bool:
    validate_manifest_core(core)
    if envelope.get("algorithm") != "Ed25519":
        return False
    public_key_text = envelope.get("public_key", "")
    if authorized_public_keys is not None and public_key_text not in authorized_public_keys:
        return False
    try:
        public_bytes = _decode_base58_bytes(public_key_text)
        signature = _decode_base58_bytes(envelope.get("signature", ""))
        if len(public_bytes) != 32 or len(signature) != 64:
            return False
        digest = bytes.fromhex(manifest_hash(core))
        encoding = envelope.get("message_encoding", "binary-v1")
        if encoding == "binary-v1":
            message = SIGNATURE_DOMAIN + digest
        elif encoding == "utf8-hex-v1":
            message = b"ORIGINCHAIN:MANIFEST-SIGNATURE:V1:UTF8-HEX:" + digest.hex().encode("ascii")
        else:
            return False
        Ed25519PublicKey.from_public_bytes(public_bytes).verify(signature, message)
    except (ValueError, InvalidSignature, ManifestError):
        return False
    return True

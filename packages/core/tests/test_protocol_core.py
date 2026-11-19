from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path

import pytest

from originchain_core import (
    ManifestError,
    canonical_json,
    content_hash_bytes,
    content_hash_stream,
    decode_id,
    manifest_hash,
    new_id,
    parse_manifest_json,
    sign_manifest,
    validate_id,
    validate_manifest_core,
    verify_manifest_signature,
)

VECTOR_PATH = Path(__file__).resolve().parents[3] / "specs/test-vectors/manifest-root-v1.json"
VECTOR = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))
CORE = VECTOR["core"]


def test_fixture_hash_canonical_form_and_signature() -> None:
    assert content_hash_bytes(VECTOR["content_bytes_utf8"].encode()) == VECTOR["content_sha256"]
    assert canonical_json(CORE).decode() == VECTOR["canonical_core_utf8"]
    assert manifest_hash(CORE) == VECTOR["manifest_hash"]

    envelope = {
        "algorithm": VECTOR["signature_algorithm"],
        "public_key": VECTOR["test_public_key_base58"],
        "signature": VECTOR["signature_base58"],
    }
    assert verify_manifest_signature(CORE, envelope)
    assert verify_manifest_signature(CORE, envelope, {envelope["public_key"]})
    assert not verify_manifest_signature(CORE, envelope, {new_id()})
    assert not verify_manifest_signature({**CORE, "content_hash": "0" * 64}, envelope)


def test_signing_matches_cross_implementation_vector() -> None:
    envelope = sign_manifest(CORE, bytes(range(32)))
    assert envelope["public_key"] == VECTOR["test_public_key_base58"]
    assert envelope["signature"] == VECTOR["signature_base58"]


def test_identifier_round_trip_and_rejects_invalid_values() -> None:
    identifier = new_id()
    assert len(decode_id(identifier)) == 32
    assert validate_id(identifier) == identifier
    for invalid in ("", "0" * 32, "1" * 32, "not-base58!", "111"):
        with pytest.raises(ValueError):
            validate_id(invalid)


def test_streaming_content_hash_matches_byte_hash() -> None:
    content = b"OriginChain" * 100_000
    assert content_hash_stream(BytesIO(content), chunk_size=777) == content_hash_bytes(content)
    assert content_hash_stream(BytesIO(b"")) == hashlib.sha256(b"").hexdigest()
    with pytest.raises(ValueError):
        content_hash_stream(BytesIO(content), chunk_size=0)


def test_canonical_json_uses_utf16_key_order_and_rejects_non_jcs_numbers() -> None:
    value = {"\ue000": 1, "\U00010000": 2}
    assert canonical_json(value).decode() == '{"𐀀":2,"":1}'
    with pytest.raises(ManifestError):
        canonical_json({"count": 1.5})
    with pytest.raises(ManifestError):
        canonical_json({"count": 9_007_199_254_740_992})
    with pytest.raises(ManifestError):
        canonical_json({"bad": "\ud800"})


def test_manifest_parser_rejects_duplicate_keys() -> None:
    with pytest.raises(ManifestError, match="duplicate"):
        parse_manifest_json('{"protocol":"originchain","protocol":"other"}')


def test_invalid_calendar_timestamp_is_rejected() -> None:
    with pytest.raises(ManifestError, match="calendar"):
        validate_manifest_core({**CORE, "created_at": "2026-02-30T03:04:05Z"})


def test_version_parent_rules_allow_branches_and_reject_reparenting() -> None:
    child = {
        **CORE,
        "version_id": new_id(),
        "manifest_id": new_id(),
        "parent_version_id": CORE["version_id"],
        "parent_manifest_hash": manifest_hash(CORE),
        "content_hash": content_hash_bytes(b"edited image bytes"),
        "size_bytes": len(b"edited image bytes"),
        "action_type": "edit",
        "relationship": "continuation",
        "created_at": "2026-01-02T03:05:05Z",
    }
    validate_manifest_core(child, parent_core=CORE)

    second_branch = {**child, "version_id": new_id(), "manifest_id": new_id(), "content_hash": content_hash_bytes(b"second edit")}
    validate_manifest_core(second_branch, parent_core=CORE)

    with pytest.raises(ManifestError, match="parent_version_id"):
        validate_manifest_core({**child, "parent_version_id": new_id()}, parent_core=CORE)
    with pytest.raises(ManifestError, match="different content"):
        validate_manifest_core({**child, "content_hash": CORE["content_hash"]}, parent_core=CORE)


def test_derivative_requires_source_reference() -> None:
    with pytest.raises(ManifestError, match="source"):
        validate_manifest_core({**CORE, "relationship": "derivative"})

#!/usr/bin/env python3
"""Verify the protocol v1 known-answer fixtures using Python stdlib + OpenSSL."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def decode_base58(value: str) -> bytes:
    number = 0
    for char in value:
        try:
            digit = ALPHABET.index(char)
        except ValueError as exc:
            raise ValueError(f"invalid base58 character: {char!r}") from exc
        number = number * 58 + digit
    body = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return b"\0" * (len(value) - len(value.lstrip("1"))) + body


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> None:
    schema_path = ROOT / "specs/manifest-schema.json"
    vector_path = ROOT / "specs/test-vectors/manifest-root-v1.json"
    semantics_path = ROOT / "specs/test-vectors/semantics-v1.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    vector = json.loads(vector_path.read_text(encoding="utf-8"))
    semantics = json.loads(semantics_path.read_text(encoding="utf-8"))
    require(schema["$schema"].endswith("2020-12/schema"), "unexpected JSON Schema draft")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    require(bool(semantics.get("scenarios")), "semantic scenarios are missing")

    core = vector["core"]
    validator.validate(core)
    invalid_root = deepcopy(core)
    invalid_root["parent_manifest_hash"] = "a" * 64
    require(not validator.is_valid(invalid_root), "schema accepted a root with a parent manifest")
    invalid_derivative = deepcopy(core)
    invalid_derivative["relationship"] = "derivative"
    require(not validator.is_valid(invalid_derivative), "schema accepted a derivative without sources")

    for identifier in (
        core["origin_id"], core["version_id"], core["manifest_id"], core["actor"]["actor_id"]
    ):
        decoded = decode_base58(identifier)
        require(len(decoded) == 32 and any(decoded), f"invalid protocol ID: {identifier}")

    content = vector["content_bytes_utf8"].encode("utf-8")
    require(len(content) == core["size_bytes"], "content size does not match fixture")
    content_hash = hashlib.sha256(content).hexdigest()
    require(content_hash == vector["content_sha256"] == core["content_hash"], "content hash mismatch")

    # This known-answer core intentionally uses only ASCII strings, integers, arrays, and null.
    # For this subset, sorted compact JSON is byte-identical to RFC 8785 JCS.
    require(all(ord(char) < 128 for char in json.dumps(core, ensure_ascii=False)), "fixture is not ASCII-only")
    canonical = json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    require(canonical == vector["canonical_core_utf8"], "canonical core mismatch")
    manifest_hash = hashlib.sha256(
        b"ORIGINCHAIN:MANIFEST:V1\0" + canonical.encode("utf-8")
    ).hexdigest()
    require(manifest_hash == vector["manifest_hash"], "manifest hash mismatch")

    signature_message = b"ORIGINCHAIN:MANIFEST-SIGNATURE:V1\0" + bytes.fromhex(manifest_hash)
    require(signature_message.hex() == vector["signature_message_hex"], "signature message mismatch")
    public_key = decode_base58(vector["test_public_key_base58"])
    signature = decode_base58(vector["signature_base58"])
    require(len(public_key) == 32 and len(signature) == 64, "invalid Ed25519 vector lengths")

    # SubjectPublicKeyInfo prefix for a raw Ed25519 public key.
    public_key_der = bytes.fromhex("302a300506032b6570032100") + public_key
    with tempfile.TemporaryDirectory(prefix="originchain-vector-") as temp_dir:
        temp = Path(temp_dir)
        (temp / "public.der").write_bytes(public_key_der)
        (temp / "message.bin").write_bytes(signature_message)
        (temp / "signature.bin").write_bytes(signature)
        subprocess.run(
            [
                "openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(temp / "public.der"),
                "-keyform", "DER", "-rawin", "-in", str(temp / "message.bin"),
                "-sigfile", str(temp / "signature.bin"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    print("OriginChain protocol v1 fixtures verified (hashes, canonical core, Ed25519 signature).")


if __name__ == "__main__":
    main()

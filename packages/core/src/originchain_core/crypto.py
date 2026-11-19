"""Content fingerprinting helpers."""

from __future__ import annotations

import hashlib
from typing import BinaryIO

DEFAULT_CHUNK_SIZE = 1024 * 1024


def content_hash_stream(stream: BinaryIO, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    digest = hashlib.sha256()
    while chunk := stream.read(chunk_size):
        digest.update(chunk)
    return digest.hexdigest()


def content_hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

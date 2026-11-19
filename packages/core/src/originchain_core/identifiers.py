"""Protocol identifier encoding and validation."""

from __future__ import annotations

import secrets

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_DIGITS = {character: index for index, character in enumerate(ALPHABET)}
IDENTIFIER_BYTES = 32


class IdentifierError(ValueError):
    """An identifier is malformed or does not represent a permitted value."""


def encode_id(raw: bytes) -> str:
    if len(raw) != IDENTIFIER_BYTES or not any(raw):
        raise IdentifierError("protocol IDs must be 32 non-zero bytes")
    number = int.from_bytes(raw, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = ALPHABET[remainder] + encoded
    leading_zeroes = len(raw) - len(raw.lstrip(b"\0"))
    return "1" * leading_zeroes + encoded


def decode_id(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise IdentifierError("protocol ID must be a non-empty base58 string")
    number = 0
    try:
        for character in value:
            number = number * 58 + _DIGITS[character]
    except KeyError as exc:
        raise IdentifierError(f"invalid base58 character: {exc.args[0]!r}") from exc
    body = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    leading_zeroes = len(value) - len(value.lstrip("1"))
    raw = b"\0" * leading_zeroes + body
    if len(raw) != IDENTIFIER_BYTES or not any(raw):
        raise IdentifierError("protocol IDs must decode to 32 non-zero bytes")
    return raw


def validate_id(value: str) -> str:
    decode_id(value)
    return value


def new_id() -> str:
    """Generate an independent protocol ID with the operating system CSPRNG."""
    while True:
        raw = secrets.token_bytes(IDENTIFIER_BYTES)
        if any(raw):
            return encode_id(raw)

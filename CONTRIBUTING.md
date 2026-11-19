# Contributing

Protocol changes must preserve cross-language determinism and be documented before implementation.

## Change process

1. Read `specs/protocol-v1.md` and `docs/DECISIONS.md`.
2. For a protocol change, update the specification, JSON schema, and conformance fixtures together.
3. Explain compatibility and migration impact in the change description.
4. Keep chain state, backend indexes, and runtime observations clearly distinguished.
5. Never include private keys, personal files, production endpoints, or credentials in commits.

## Conformance

Implementations must produce the same canonical manifest bytes and hashes from `specs/test-vectors/`. Add fixtures for new normative behavior. A fixture is not a substitute for executable tests; each implementation milestone must add and run its own tests before being marked complete.

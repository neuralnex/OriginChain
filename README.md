# OriginChain

OriginChain is an open provenance protocol for digital content. It gives assets persistent identities, records immutable content versions, and lets people verify a file against signed manifests and Solana commitments.

The first product milestone defines the protocol. The first user-facing MVP will focus on images and video; the protocol stays media-agnostic so additional content types can be added through registered media types and extensions.

## Project status

**Completed:** Protocol v1, Python/TypeScript cryptographic core, local Solana program build, and M4 backend implementation.\
**Next milestone:** Run the backend locally, connect staging/devnet, and build the indexer and runtime.\
**Blockchain:** Solana (confirmed).\
**Program stack:** Rust + Anchor 1.2.2; Solana CLI 4.4.1.\
**Backend stack:** Python/FastAPI with SQLAlchemy and Alembic; SQLite for local startup and PostgreSQL configuration for deployment. Rust runtime and Next.js/TypeScript remain planned.

See [the implementation status](docs/IMPLEMENTATION_STATUS.md), [development plan](docs/DEVELOPMENT_PLAN.md), and [protocol v1](specs/protocol-v1.md). The reference core lives in `packages/core/` and `packages/sdk-js/`.

## Core rule

Content bytes determine a version's integrity fingerprint. A transmission, copy, move, rename, or unchanged download preserves the same asset and version. A byte-changing edit creates a new version. Independent edits can branch from the same parent.

## Repository map

- `specs/` protocol, schemas, and conformance vectors
- `packages/core/` Python protocol reference code
- `programs/originchain/` Anchor registry and LiteSVM scenarios
- `backend/` FastAPI, persistence, chain adapter, and verification API
- `runtime/` local-first cross-platform observer (planned)
- `packages/sdk-js/`, `packages/sdk-python/` developer SDKs (planned)
- `apps/explorer/` asset explorer and verification UI (planned)
- `integrations/` application integration interfaces (planned)
- `os/` long-term dedicated OS work (future)

## Development

Install the Python development requirements in a virtual environment, then run the reference core tests with `PYTHONPATH=packages/core/src python -m pytest packages/core/tests`. Run the TypeScript SDK checks with `npm ci && npm test` from `packages/sdk-js/`. Build the on-chain program with `anchor build`; its LiteSVM scenario is run with `cargo test -p originchain-program --test protocol_litesvm` after the build. See `Anchor.toml` and `programs/originchain/README.md`.

Do not put private keys, API tokens, or production credentials in this repository.

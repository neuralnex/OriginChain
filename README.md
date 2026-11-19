# OriginChain

OriginChain is an open provenance system for digital content. Its goal is to assign images and videos an identity at capture or import, preserve that identity across devices and applications, record content changes as versions, and let anyone verify signed manifests and Solana commitments.

The product has two parts: cloneable open-source OS/application adapters, and the hosted OriginChain platform for collaboration and media/file sharing. Users can build adapters from this repository or point them to a compatible self-hosted service. The founder-funded launch is free to users, with fair-use limits to control storage, bandwidth, and sponsored chain costs. The next milestone is an opt-in Linux runtime; native macOS, Windows, Android, and iOS adapters follow. Coverage depends on each platform's permissions and integrations.

## Project status

**Completed:** Protocol v1, Python/TypeScript cryptographic core, Solana program deployed and initialized on devnet, backend API, and a browser registration flow for Phantom.\
**Current MVP flow:** Connect Phantom on devnet, select an image/video, sign its manifest and registration transaction, and submit to the devnet API.\
**Blockchain:** Solana (confirmed).\
**Program stack:** Rust + Anchor 1.2.2; Solana CLI 4.4.1.\
**Backend stack:** Python/FastAPI with SQLAlchemy and Alembic; SQLite for local startup and PostgreSQL configuration for deployment. Collaboration, managed object storage, sponsored registration, and native adapters remain planned.

See [the implementation status](docs/IMPLEMENTATION_STATUS.md), [development plan](docs/DEVELOPMENT_PLAN.md), and [protocol v1](specs/protocol-v1.md). The reference core lives in `packages/core/` and `packages/sdk-js/`.

## Core rule

Content bytes determine a version's integrity fingerprint. A transmission, copy, move, rename, or unchanged download preserves the same asset and version. A byte-changing edit creates a new version. Independent edits can branch from the same parent.

## Repository map

- `specs/` protocol, schemas, and conformance vectors
- `packages/core/` Python protocol reference code
- `programs/originchain/` Anchor registry and LiteSVM scenarios
- `backend/` FastAPI, persistence, chain adapter, and verification API
- `runtime/` early local-first Linux image/video observer (see [runtime README](runtime/daemon/README.md))
- `packages/sdk-js/`, `packages/sdk-python/` developer SDKs (planned)
- `apps/explorer/` browser registration app (Vite + TypeScript)
- `integrations/` application integration interfaces (planned)
- `os/` long-term dedicated OS work (future)

See [Device Runtime v1](specs/runtime-v1.md) and [Hosted Platform v1](specs/platform-v1.md) for adapter, collaboration, funding, and privacy requirements.

## Development

Install the Python development requirements in a virtual environment, then run the reference core tests with `PYTHONPATH=packages/core/src python -m pytest packages/core/tests`. Run the TypeScript SDK checks with `npm ci && npm test` from `packages/sdk-js/`. Build the on-chain program with `anchor build`; its LiteSVM scenario is run with `cargo test -p originchain-program --test protocol_litesvm` after the build. See `Anchor.toml` and `programs/originchain/README.md`.

Do not put private keys, API tokens, or production credentials in this repository.

## Run the devnet registration app

Use two terminals from the repository root. Start the API with the devnet adapter and local SQLite database:

```sh
CHAIN_ADAPTER=solana DATABASE_URL=sqlite:///./originchain.db SOLANA_RPC_URL=https://api.devnet.solana.com SOLANA_PROGRAM_ID=J6grB9Db5FjKYkGLWf4n81BZg75WEE9KVXbnq5XZBcg1 PYTHONPATH=backend:packages/core/src venv/bin/python -m uvicorn app.main:app --reload
```

In the second terminal, install and start the Explorer:

```sh
cd apps/explorer
npm install
npm run dev
```

Open `http://127.0.0.1:5173`, switch Phantom to Solana Devnet, connect, select an image or video, then approve both the manifest signature and transaction. The API verifies the file and resulting on-chain accounts before saving the provenance record. Configure a different API with `VITE_API_URL` and a different RPC endpoint with `VITE_SOLANA_RPC_URL` before starting Vite.

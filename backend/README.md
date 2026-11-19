# OriginChain API

The first backend slice accepts signed image and video manifests, fingerprints the exact uploaded bytes in memory, stores the manifest and provenance metadata, and returns asset/version history. Media bytes are never written to the database or object storage by these endpoints.

## Local setup

From the repository root:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e backend
PYTHONPATH=backend:packages/core/src uvicorn app.main:app --reload
```

By default the API uses SQLite and a deterministic `mock` chain adapter. The API starts at `http://127.0.0.1:8000`; OpenAPI docs are at `/docs`. Mock commitments are development records and verification returns `incomplete`, never `verified`.

For PostgreSQL and Solana devnet, configure `DATABASE_URL`, `CHAIN_ADAPTER=solana`, and `SOLANA_RPC_URL` in the process environment or the repository `.env`. The client must submit a wallet-signed serialized transaction in `transaction_base64`; the server does not hold wallet keys. The RPC adapter waits for confirmation and checks the resulting OriginChain account bytes against the manifest before persisting the record.

For migration-managed environments, turn off automatic table creation and run from the backend directory:

```sh
alembic upgrade head
```

Configuration variables: `DATABASE_URL`, `CHAIN_ADAPTER` (`mock` or `solana`), `SOLANA_RPC_URL`, `SOLANA_PROGRAM_ID`, `MAX_UPLOAD_BYTES`, `REQUEST_TIMEOUT_SECONDS`, and `AUTO_CREATE_TABLES`.

## API surface

- `GET /v1/health`
- `POST /v1/assets`
- `GET /v1/assets/{origin_id}`
- `GET /v1/assets/{origin_id}/history`
- `GET /v1/assets/{origin_id}/versions`
- `POST /v1/assets/{origin_id}/versions`
- `GET /v1/versions/{version_id}?origin_id=...`
- `GET /v1/versions/{version_id}/manifest?origin_id=...`
- `POST /v1/verify`

Registration and version creation require a manifest, detached Ed25519 signature envelope, Base64 content bytes, and optionally an idempotency key header. With the Solana adapter, include the wallet-signed transaction. Requests are bounded by `MAX_UPLOAD_BYTES`; content is hashed and discarded after request handling.

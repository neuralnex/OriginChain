# OriginChain Solana program

Anchor program implementing the first protocol registry milestone.

## Instructions

- `initialize_registry`: create the singleton registry and set its authority.
- `set_paused`: allow the registry authority to stop or resume new registrations and versions.
- `register_asset`: create an asset PDA and its immutable root version.
- `create_version`: create a child version after checking parent existence, distinct content hash, and creator/editor authorization.
- `grant_editor` / `revoke_editor`: manage per-asset editor permission PDAs. An expiry of `0` means no expiry; other expiries are Unix seconds.

## Accounts

- Registry PDA: `["registry"]`.
- Asset PDA: `["asset", origin_id]`.
- Version PDA: `["version", origin_id, version_id]`.
- Editor grant PDA: `["editor", origin_id, editor_pubkey]`.

All IDs and hashes are passed as fixed 32-byte values, not UTF-8 strings. IDs must not be all zeroes. The off-chain canonical manifest hash is stored as the commitment; no content bytes are stored on-chain. `manifest_uri_hash` is a commitment to an optional off-chain locator and is zero when unused.

The on-chain `created_at` and `sequence` describe chain ordering. The signed manifest retains its separate claimed timestamp. Version sequence is a per-Origin ordering hint, not identity; concurrent branches are valid.

The current program ID is backed by a local development keypair in the ignored `target/deploy/` directory. It exists only for local builds and tests. Never use that keypair for a production deployment; generate a production program ID and follow a separate deployment process.

## Current limits

The first program milestone does not implement publisher credentials, private visibility, a transfer instruction, storage, or a full application event ledger. Root source references and derivative/composition policy remain represented in the signed off-chain manifest; the on-chain core focuses on asset identity, version ancestry, commitments, and authorization.

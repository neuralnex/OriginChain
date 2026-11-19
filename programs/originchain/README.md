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

The current program ID is backed by a development keypair in the ignored `target/deploy/` directory. It can be used for devnet deployment and testing, but never for mainnet; generate and audit a separate program ID/keypair for a production deployment.

## Devnet deployment

`Anchor.toml` targets devnet. The configured CLI payer wallet must exist and have devnet SOL before deployment. If you do not already have a CLI wallet, create a devnet-only keypair with `solana-keygen new --outfile ~/.config/solana/id.json`; keep its recovery phrase private and offline. Then run:

```sh
solana airdrop 2 --url devnet
solana balance --url devnet
anchor build
anchor deploy --provider.cluster devnet
solana program show J6grB9Db5FjKYkGLWf4n81BZg75WEE9KVXbnq5XZBcg1 --url devnet
venv/bin/python scripts/initialize_registry.py
```

The last command creates the registry PDA needed before asset registration. It is safe to run again after initialization. Never paste or commit wallet key material.

The program is deployed on devnet at `J6grB9Db5FjKYkGLWf4n81BZg75WEE9KVXbnq5XZBcg1`; its registry PDA is `7FUEykZ6H2KhLokQcFqzhgNnn7Hy1HTsrC6MLCc6DKL6`. The program account's current upgrade authority is the configured devnet payer wallet.

## Current limits

The first program milestone does not implement publisher credentials, private visibility, a transfer instruction, storage, or a full application event ledger. Root source references and derivative/composition policy remain represented in the signed off-chain manifest; the on-chain core focuses on asset identity, version ancestry, commitments, and authorization.

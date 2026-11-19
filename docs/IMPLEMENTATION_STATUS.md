# Implementation status

Updated: 2026-11-19

## Completed milestones

- [x] M1 protocol specification, manifest schema, lifecycle scenarios, and cryptographic known-answer vector.
- [x] M2 Python and TypeScript reference cores for identifiers, streaming SHA-256, canonical manifests, Ed25519 signatures, and version relationship validation.

## Current

- [x] Product scope recorded: universal provenance infrastructure; image and video MVP; open media-type extension.
- [x] Solana selected as the chain.
- [x] Solana CLI 4.4.1 and Anchor CLI 1.2.2 installed; rustup Rust 1.100.0 selected for builds.
- [x] Manifest schema validated against valid and invalid root cases.
- [x] Python and TypeScript implementations match the same canonical manifest hash and Ed25519 signature vector.
- [ ] Add a general RFC 8785 implementation comparison for non-ASCII and edge-case strings before protocol release.
- [x] Solana program: Anchor instructions, SBF artifact, generated IDL, and LiteSVM scenarios build successfully.
- [x] Anchor build ran the Rust unit and LiteSVM targets successfully.
- [x] Backend API implementation: signed image/video registration, branching versions, history/manifests, upload limits, idempotency, SQLAlchemy records, Alembic migration, mock adapter, and Solana RPC adapter.
- [x] File verification endpoint distinguishes verified, unverified, tampered, and incomplete; mock records never report verified.
- [x] Anchor project now targets devnet and includes a registry initialization utility.
- [x] Deployed OriginChain program to Solana devnet and initialized the registry PDA.
- [x] Added a Vite/TypeScript browser registration app for Phantom devnet, including detached manifest signing, on-chain register-asset transaction construction, and API submission.
- [x] Enabled local Explorer-to-API CORS origins.
- [x] Install Explorer npm dependencies and build the browser app successfully.
- [x] User completed an end-to-end Phantom image registration; API confirmed and validated the devnet transaction and resulting accounts.
- [x] User ran the backend with SQLite and the Solana devnet adapter for that registration.
- [ ] Exercise PostgreSQL deployment configuration.
- [ ] Event indexer and reconciliation worker.
- [ ] Portable object format.
- [ ] Runtime and application integrations.
- [x] Defined the device-runtime coverage model and iOS/macOS/Windows/Linux/Android delivery order in `specs/runtime-v1.md`.
- [x] Recorded the open-source adapters + hosted collaboration platform model and founder-funded free launch in `specs/platform-v1.md`.
- [x] R1 runtime protocol details, device-local signed identities, state model, permission controls, and reconciliation rules documented in `specs/runtime-v1.md`.
- [x] R2 early Linux local identity observer implemented in `runtime/daemon`: selected-folder watching, SQLite index, local signed sidecars/events, streaming image/video hashes, pause/exclusion controls, and restart reconciliation.
- [ ] Manually smoke-run Linux runtime lifecycle: new file, unchanged restart, copied file, changed tracked file, exclusion, and pause/resume. No media upload or chain write is part of this slice.
- [ ] Hosted user/team accounts, collaboration permissions, managed media/file sharing, and object storage.
- [ ] Sponsored Solana registration with bounded platform payer and user creator identity.
- [ ] Explorer history, verification, and version creation screens.

## Environment

Python 3.12, rustup Rust 1.100.0, Solana CLI 4.4.1, Anchor CLI 1.2.2, Node 22, npm, and TypeScript 5.2 are present. The shell may need `PATH="$HOME/.cargo/bin:$HOME/.local/share/solana/install/active_release/bin:$PATH"` to select the installed toolchains.

## Verification

- `PYTHONPATH=packages/core/src python -m pytest packages/core/tests`: 9 passed.
- `npm test` in `packages/sdk-js`: TypeScript build and protocol vector tests passed.
- `scripts/verify_protocol_vectors.py`: JSON Schema, content hash, canonical bytes, manifest hash, and Ed25519 vector passed.
- `git diff --check`: passed.
- `cargo build -p originchain-runtime`: passed; watcher lifecycle has not yet been exercised manually.
- `cargo check -p originchain-program --lib` with Rust 1.100.0: passed.
- `cargo check -p originchain-program --test protocol_litesvm`: passed; this compiles the scenario target without executing it.
- `anchor build`: passed after fetching the missing `serde_spanned` crate. It generated `target/deploy/originchain_program.so` and `target/idl/originchain_program.json`, and ran unit/LiteSVM targets successfully. Anchor/Solana emitted non-fatal macro `cfg` and LTO warnings.
- Program keypair public key matches the configured localnet program ID: `J6grB9Db5FjKYkGLWf4n81BZg75WEE9KVXbnq5XZBcg1`.
- Devnet program: `J6grB9Db5FjKYkGLWf4n81BZg75WEE9KVXbnq5XZBcg1`.
- Devnet registry PDA: `7FUEykZ6H2KhLokQcFqzhgNnn7Hy1HTsrC6MLCc6DKL6`.
- Devnet ProgramData: `6FAXEDjK8pCYSV5SVZK2bbAPtZZhQ9BCx8s4v3bvoehR`; upgrade authority is the configured devnet payer wallet.

## Completion record

M1, M2, local M3, and the devnet deployment/registry initialization are complete. The current RFC 8785 known-answer fixture contains only ASCII strings; a wider cross-language Unicode/string suite remains before protocol release. The global Solana CLI endpoint remains mainnet; project Anchor commands target devnet through `Anchor.toml`.

The browser registration and API-to-devnet transaction path has been demonstrated by the user with a real image. The backend does not store submitted media bytes. Solana-backed registration requires a wallet-signed transaction; the repository contains no server-side signing key. The Linux runtime is early development: it builds, but the local lifecycle still needs a manual smoke run; portable export/import is not implemented.

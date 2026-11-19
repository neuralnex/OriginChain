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
- [ ] Backend, indexer, and verification API.
- [ ] Portable object format.
- [ ] Runtime and application integrations.
- [ ] Explorer.

## Environment

Python 3.12, rustup Rust 1.100.0, Solana CLI 4.4.1, Anchor CLI 1.2.2, Node 22, npm, and TypeScript 5.2 are present. The shell may need `PATH="$HOME/.cargo/bin:$HOME/.local/share/solana/install/active_release/bin:$PATH"` to select the installed toolchains.

## Verification

- `PYTHONPATH=packages/core/src python -m pytest packages/core/tests`: 9 passed.
- `npm test` in `packages/sdk-js`: TypeScript build and protocol vector tests passed.
- `scripts/verify_protocol_vectors.py`: JSON Schema, content hash, canonical bytes, manifest hash, and Ed25519 vector passed.
- `git diff --check`: passed.
- `cargo check -p originchain-program --lib` with Rust 1.100.0: passed.
- `cargo check -p originchain-program --test protocol_litesvm`: passed; this compiles the scenario target without executing it.
- `anchor build`: passed after fetching the missing `serde_spanned` crate. It generated `target/deploy/originchain_program.so` and `target/idl/originchain_program.json`, and ran unit/LiteSVM targets successfully. Anchor/Solana emitted non-fatal macro `cfg` and LTO warnings.
- Program keypair public key matches the configured localnet program ID: `J6grB9Db5FjKYkGLWf4n81BZg75WEE9KVXbnq5XZBcg1`.

## Completion record

M1, M2, and local M3 acceptance checks pass. The current RFC 8785 known-answer fixture contains only ASCII strings; a wider cross-language Unicode/string suite remains before protocol release. The program has not been deployed to devnet.

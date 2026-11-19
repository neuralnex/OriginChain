# OriginChain build context

## Product direction

OriginChain assigns persistent identities to images and videos at creation or import, preserves identity through unchanged transfer, records byte-changing versions, and enables independent verification. The protocol accepts more media types over time.

The long-term product combines cloneable open-source device/application adapters with a hosted collaboration platform for workspaces, media/files, sharing, and provenance. Users may self-host or configure a compatible endpoint. The founder funds initial hosted operation; usage has configurable fair-use and abuse limits, and users are not billed at launch unless policy is deliberately changed. See `specs/platform-v1.md` and `specs/runtime-v1.md`.

The native, permission-aware device runtime targets Linux, macOS, Windows, Android, and iOS. It gives media identity wherever OriginChain has an authorized capture, import/share, watched-folder, media-library, or app-integration surface. Do not promise universal monitoring: mobile and desktop operating systems restrict third-party access to files and other apps' private storage.

Core invariant: transmission, copying, moving, renaming, and unchanged download do not create versions. Byte-changing edits do. A local identity is not automatically chain-registered or visible on another device. Cross-device continuity requires a carried signed provenance package or a public registry commitment. Chain registration is an explicit user action because it publishes a content hash; the hosted platform may sponsor transaction costs.

## Decisions and stack

- Solana is selected and the Anchor program is deployed to devnet with its registry initialized.
- Python + FastAPI backend and TypeScript/Vite browser registration app are implemented.
- Rust is the intended local runtime implementation; SQLite is intended for local state.
- Python, Rust, and TypeScript implementations must agree on the language-independent protocol.
- Protocol v1 uses random 32-byte IDs, exact-byte SHA-256, RFC 8785 canonical JSON, Ed25519 signatures, and a version DAG.
- Images and video are the MVP media. The chain stores commitments, never media bytes.
- Device monitoring is opt-in, local-first, visible, pausable, and configurable with exclusions.

## Current state and next milestone

The user has successfully registered a first image on Solana devnet from the Phantom browser flow. The repository has no device runtime implementation yet. The next milestone is R1 runtime protocol details followed by R2, a Linux user service for opted-in folders, local SQLite identity/event state, streaming fingerprints, and restart reconciliation. Do not start with kernel drivers, auto-publishing, or broad mobile permissions.

## Product lifecycle

Capture/import -> assign local Origin ID and root Version ID -> hash exact media bytes -> make a signed local manifest -> optionally look up a known version -> preserve identity in a signed portable package or explicit chain registration -> record edits only with an evidenced parent/action -> verify file, manifest, and optional chain commitment.

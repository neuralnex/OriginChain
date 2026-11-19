# OriginChain build context

## Product

OriginChain is open digital content provenance infrastructure. It assigns stable asset identities, signs manifests for exact byte states, records immutable versions and branches, and supports independent verification. Initial user workflows focus on images and video; the protocol accepts other media types through its open media type field.

Product layers: protocol; Solana program and platform (API, indexer, verification, storage, Explorer, developer tools); opt-in local-first OS runtime; dedicated OS as a long-term vision.

Core invariant: transmission, copying, moving, renaming, and unchanged download do not create a new version. Byte-changing edits do. Media and private identity evidence stay off-chain. A signature and chain commitment do not establish that a real-world authorship or application claim is true.

## Decisions and stack

- Solana is selected.
- Rust + Anchor, Python + FastAPI, PostgreSQL, a Rust runtime with SQLite, TypeScript/Next.js, and TypeScript/Python SDKs are the supplied blueprint's recommended stack. Only Solana has been explicitly selected; confirm the remaining choices before their implementation milestones.
- Protocol v1 is the current milestone. It uses 32-byte random identifiers, SHA-256 of exact file bytes, RFC 8785 canonical JSON, Ed25519 signatures with domain separation, and a version DAG with one primary parent and optional source references.
- Initial on-chain strategy: one independently verifiable record per version; no media bytes on chain.
- Initial privacy model: explicit registration and public commitments; no claim of private on-chain registration.

## Current milestone and environment

M1, M2, and M3 are complete for local development: protocol specification/schema/fixtures, Python and TypeScript reference cores, and the Anchor program with LiteSVM scenarios. `anchor build` passes and produces an SBF program and IDL. Anchor's build ran the Rust unit and LiteSVM scenario targets successfully. No devnet deployment has occurred. The environment has Rust 1.100.0, Solana CLI 4.4.1, and Anchor CLI 1.2.2.

Build status:

```yaml
milestones:
  - M1: complete
  - M2: complete
  - M3: complete
mvp_complete: false
core_tests_passing: true
program_build: passed
program_tests: passed
devnet_deployed: false
program_id: J6grB9Db5FjKYkGLWf4n81BZg75WEE9KVXbnq5XZBcg1
```

## Product acceptance path

Register an image/video -> sign manifest -> commit to Solana -> preserve identity over transfer -> edit into version(s) including parallel branches -> verify file, signature, parent relationships, and chain evidence independently. Later: portable object, offline runtime reconciliation, integrations, SDKs, and Explorer.

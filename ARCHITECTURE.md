# OriginChain architecture

OriginChain is a protocol, a Solana-backed platform, and a local-first runtime. The components share a versioned, language-independent protocol contract.

## System boundaries

1. **Protocol:** identifiers, byte hashing, canonical manifests, signatures, event semantics, version graph rules, and verification outcomes.
2. **Solana program:** ownership and editor authorization, asset/version commitments, and indexable events. Media bytes and private identity evidence remain off-chain.
3. **Backend:** authenticated API, object storage adapter, chain submission, indexer, and verification services. Its database is an index/cache, not the authority for chain commitments.
4. **Open adapters:** cloneable, permission-aware OS/app connectors that create local identities and synchronize with a configurable hosted or self-hosted endpoint.
5. **Hosted platform:** workspaces, collaboration permissions, off-chain media/file sharing, history, verification, and chain registration.
6. **SDKs and integrations:** signed declarations from applications and reusable protocol operations.
7. **Dedicated OS:** long-term possibility, contingent on a stable protocol/runtime and security review. The first product is native adapters and services on existing operating systems.

## Data flow

The capture app or permitted device runtime hashes exact file bytes and creates a local identity and signed manifest. It can sync the manifest and an authorized media object to a hosted or self-hosted platform. A user may request chain registration; the user's signature identifies the creator while a platform sponsor may pay transaction fees and account rent. An indexer records the transaction reference. A verifier can independently recompute the file hash, validate the manifest signature, and check the chain commitment without trusting the backend's answer.

The first release favors one independently verifiable on-chain record per version. Batching commitments under Merkle roots is deferred until inclusion proofs and availability rules are specified.

## Trust and privacy

On-chain records are public. The MVP therefore requires explicit user registration and makes no claim that an on-chain content hash is private. Media bytes, legal names, and credential evidence stay off-chain. Hash equality proves byte equality only; it does not prove authorship, truthful application behavior, or the real-world identity of an actor.

## Initial implementation boundaries

Protocol v1 is media-agnostic. Image and video workflows are the first acceptance scenarios. Runtime monitoring is opt-in and local-first. The platform roadmap starts with a Linux service, then macOS/Windows desktop adapters, then Android/iOS native capture and share surfaces. See [Device Runtime v1](specs/runtime-v1.md) for coverage boundaries and gates.

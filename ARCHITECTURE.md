# OriginChain architecture

OriginChain is a protocol, a Solana-backed platform, and a local-first runtime. The components share a versioned, language-independent protocol contract.

## System boundaries

1. **Protocol:** identifiers, byte hashing, canonical manifests, signatures, event semantics, version graph rules, and verification outcomes.
2. **Solana program:** ownership and editor authorization, asset/version commitments, and indexable events. Media bytes and private identity evidence remain off-chain.
3. **Backend:** authenticated API, object storage adapter, chain submission, indexer, and verification services. Its database is an index/cache, not the authority for chain commitments.
4. **Runtime:** opt-in local file observation, hashing, event queue, and reconciliation. It must not block ordinary saves or silently upload content.
5. **SDKs and integrations:** signed declarations from applications and reusable protocol operations.
6. **Explorer:** history and verification UI that distinguishes actual chain evidence from demo or backend-only data.
7. **Dedicated OS:** long-term direction, contingent on a stable protocol/runtime and security review.

## Data flow

The client hashes exact file bytes, creates and signs a canonical manifest, and requests registration or version creation. The backend validates the request and submits a commitment to Solana. An indexer records the transaction reference. A verifier can independently recompute the file hash, validate the manifest signature, and check the chain commitment without trusting the backend's answer.

The first release favors one independently verifiable on-chain record per version. Batching commitments under Merkle roots is deferred until inclusion proofs and availability rules are specified.

## Trust and privacy

On-chain records are public. The MVP therefore requires explicit user registration and makes no claim that an on-chain content hash is private. Media bytes, legal names, and credential evidence stay off-chain. Hash equality proves byte equality only; it does not prove authorship, truthful application behavior, or the real-world identity of an actor.

## Initial implementation boundaries

Protocol v1 is media-agnostic. Image and video workflows are the first acceptance scenarios. Runtime monitoring is opt-in and local-first. Platform-specific filesystem adapters, broad integrations, and a dedicated OS follow the protocol, verification, and Linux runtime foundations.

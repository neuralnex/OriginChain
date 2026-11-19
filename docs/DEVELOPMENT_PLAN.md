# Development plan

Milestones are gated by demonstrated behavior. The dedicated OS is a long-term goal and does not block the first product.

| Milestone | Deliverable | Acceptance gate |
| --- | --- | --- |
| M1 Protocol | Normative protocol v1, schema, fixtures, decision log | IDs, hashes, signatures, event semantics, and branching are unambiguous and cross-language test vectors are published. |
| M2 Cryptographic core | Python reference core, then matching TypeScript/Rust implementations | Identical file hashes, canonical bytes, manifest hashes, and signature verification across languages. |
| M3 Solana program | Anchor registry, asset/version accounts, authorization, events | LiteSVM scenarios cover registration, branches, unchanged-content rejection, editor grants/revocation, and unauthorized calls. |
| M4 Backend | FastAPI, PostgreSQL/SQLite, migrations, API, chain adapter | API contracts, idempotency, signed manifests, and local mock flow work; Solana adapter confirms wallet-signed account commitments. |
| M5 Verification/indexer | Independent chain and manifest verification | Verifier distinguishes verified, unverified, tampered, and incomplete evidence. |
| M6 Portable object | Versioned archive with safe import/export | Round trips preserve content and IDs; malformed archives and path traversal are rejected. |
| M7 Runtime foundation | Rust local service, SQLite queue, Linux observer | Opt-in observation and offline reconciliation work without blocking saves. |
| M8 SDKs/integrations | TypeScript and Python SDKs, signed app declarations | A sample image/video integration creates a version and preserves branch semantics. |
| M9 Explorer | Asset, verification, and version graph views | Chain-backed evidence is distinguished from mock or backend-only data. |
| M10 Security/interoperability | Threat review, adversarial tests, independent implementation exercise | Protocol and service boundaries are reviewed before mainnet planning. |
| M11 Mainnet preparation | Operations, monitoring, recovery, deployment controls | Audited program and operational readiness are complete before any production launch. |
| M12 Dedicated OS research | Requirements and feasibility only | Starts after protocol/runtime stability and user demand. |

## Current milestone scope

M1 and M2 are complete: the contract is documented and Python/TypeScript implementations agree on the same signed known-answer vector. M3 builds locally; no devnet deployment has occurred. M4 now has an API implementation, persistence models and migration, local mock mode, wallet-signed Solana RPC adapter, and file verification endpoint. The backend has not yet been installed or exercised against PostgreSQL/devnet in this workspace.

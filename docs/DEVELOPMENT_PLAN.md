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
| M7 Runtime protocol | Local identity states, privacy/coverage model, device keys, reconciliation contract | Device identity, registered identity, and authorship claims are clearly distinct. |
| M8 Linux runtime | Rust user service, SQLite, selected-folder observer, local image/video IDs | Local identity survives restart; pause/exclusions/reconciliation work; no content upload or chain write happens silently. |
| M9 Hosted collaboration platform | User/team accounts, workspaces, roles, private media/file sharing, history | Authorized collaborators can share and retrieve encrypted objects; deletion and public-chain limits are clear. |
| M10 Sponsored registration | Sponsor-paid devnet tx/rent, user-signed claims, budget/rate controls | Chain records retain the user as creator; sponsor cost is isolated, limited, auditable, and explicit in UX. |
| M11 Portable identity | Signed provenance package and runtime-platform sync handoff | A copied package verifies on another device; an ordinary file transfer adds no version. |
| M12 Desktop platforms | Native macOS and Windows permission, watcher, and share/file-manager adapters | Selected locations work with accurate coverage and restart recovery. |
| M13 Mobile platforms | Native Android and iOS capture/import/share apps and permission-limited library integrations | Users can assign identity at capture/import; limited media access and background limits are surfaced honestly. |
| M14 SDKs and Explorer | App declarations, asset/history/verification screens | Apps can create semantic events; explorer distinguishes local, claimed, and chain-verified evidence. |
| M15 Security/interoperability | Threat review, independent implementation exercise, recovery controls | Trust and privacy boundaries are reviewed before mainnet planning. |
| M16 Production preparation | Operations, monitoring, program and update security | Audited program and operational readiness before broad distribution. |

## Current milestone scope

M1-M4 and the devnet program/registry are in place. The browser has registered an image on devnet. The next build milestone is the Linux local-identity runtime, followed by hosted collaboration and sponsored registration. There is no device runtime, user/team authentication, managed media storage, or sponsored transaction service yet. Mobile and desktop support must use separate native adapters and honor platform permission boundaries.

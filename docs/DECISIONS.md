# Protocol and architecture decisions

Status: initial decisions for protocol v1. Changes require a versioning note and updated conformance fixtures.

| ID | Decision | Reason / consequence |
| --- | --- | --- |
| D-001 | `OriginID`, `VersionID`, `EventID`, `ActorID`, and `ManifestID` are independent random 32-byte values from a CSPRNG, encoded as base58. | IDs do not depend on file paths, timestamps, or hashes. A detected collision is rejected; IDs are never merged. |
| D-002 | SHA-256 over exact file bytes is the required integrity hash. | Streaming implementations can handle large files. Perceptual hashes may aid discovery but are never identity or integrity proof. |
| D-003 | Canonical manifest serialization uses RFC 8785 JSON Canonicalization Scheme (JCS), UTF-8, with duplicate keys rejected. | Python, Rust, and TypeScript must produce identical bytes. No extra Unicode normalization is applied. |
| D-004 | A manifest hash is `SHA256("ORIGINCHAIN:MANIFEST:V1\0" || JCS(core))`; the Ed25519 signature covers `"ORIGINCHAIN:MANIFEST-SIGNATURE:V1\0" || manifest_hash_bytes`. `ManifestID` remains a separate random ID. | Domain separation prevents cross-purpose signature reuse. The signature envelope and operational chain/storage references are outside the hashed core. |
| D-005 | Root versions have `parent_version_id = null`; every non-root version has exactly one primary parent from the same Origin. Additional source assets are references, not extra primary parents. | This gives each asset a primary-parent DAG while allowing composition provenance. |
| D-006 | A version records a distinct byte state. A byte-changing continuation or derivative creates a version; an unchanged transfer or file-management operation does not. | A changed derivative may use a new Origin ID and cite source assets. Format conversion changes bytes and must be declared as `transform`. |
| D-007 | Byte-identical registrations are not automatically merged. | Identity is an explicit publisher action; equal hashes alone do not establish common authorship or intent. |
| D-008 | Public Solana commitments are the initial visibility model. Registration is explicit; private media and real-world identity evidence stay off-chain. | Public hashes can be matched against known files. Private or selective-disclosure commitments need a separate design. |
| D-009 | Protocol v1 supports anonymous, pseudonymous, and credentialed identity modes, but identity mode makes no claim about real-world verification. | Credential validation and issuer trust are separate services and are not inferred from a wallet signature. |
| D-010 | A content-hash mismatch is `tampered` only when a specific trusted version is claimed. With no matching record the result is `unverified`; missing required evidence is `incomplete`. | Verification outcomes avoid treating every unknown file as malicious. |
| D-011 | The protocol accepts any syntactically valid media type. The first product workflows and acceptance examples target images and video. | New media types do not require a protocol fork. |
| D-012 | Each version is independently committed on-chain in the first implementation; Merkle batching is deferred. | Simpler verification and authorization semantics for the first usable release. |
| D-013 | Manifest signature envelopes may select `utf8-hex-v1` to sign a readable ASCII representation of the manifest digest when wallet providers misclassify binary signatures as transaction requests; omitted encoding remains the original binary-v1 profile. | Keeps existing signatures verifiable and avoids ambiguous binary payloads in wallet message-signing APIs. |
| D-014 | OriginChain combines open-source, cloneable OS/application adapters with a hosted collaboration and media/file-sharing platform; adapters must also support a replaceable/self-hosted endpoint. | Keeps device integration extensible and user data portable while giving teams a usable shared product. |
| D-015 | The initial hosted platform is free to users and founder-funded, including configured infrastructure and sponsored Solana costs; fair-use ceilings, rate limits, and sponsor budgets are required before external beta. | Honors founder-funded launch intent while bounding storage, bandwidth, and transaction exposure. User billing requires a later deliberate decision. |

## Deferred decisions

- Publisher wallet signature versus deferred registration and how a deferred actor is authorized.
- Runtime device key enrollment, hardware key use, rotation, recovery, and revocation.
- Application signing identity and accepted credential issuers.
- Visibility beyond public commitments and a privacy-preserving commitment construction.
- Version sequence allocation across concurrent writers; IDs remain the stable identity and sequence is only a per-origin ordering hint.
- Retention, availability, and encryption policy for off-chain manifests and portable objects.
- How a “logical edit with identical bytes” should be represented. It cannot create a new content version under the byte-state rule, but an event may record the declaration.

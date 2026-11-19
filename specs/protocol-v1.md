# OriginChain Protocol v1

Status: draft for implementation. This document defines the first interoperable protocol contract. Changes before implementation should update this document, `manifest-schema.json`, the fixture set, and `docs/DECISIONS.md` together.

## 1. Scope and guarantees

OriginChain records claims about digital content and makes selected commitments independently verifiable. It does not prove that an actor created content, that an application behaved honestly, or that a claimed timestamp is true. A valid signature proves that a key signed the specified bytes.

Protocol v1 is media-agnostic. Initial product flows focus on image and video content. Media types outside that scope use the same identity, hashing, manifest, and version rules.

## 2. Terms and identifiers

| Identifier | Meaning |
| --- | --- |
| `OriginID` | Persistent identity for one explicitly registered asset lineage. |
| `VersionID` | Identity of one immutable byte state within an Origin. |
| `EventID` | Identity of one declared or observed operation; an event need not create a version. |
| `ActorID` | Pseudonymous identity for a person, application, device, organization, or unknown actor. |
| `ManifestID` | Random identity of a signed manifest, independent of its content hash. |

Origin, Version, Event, Actor, and Manifest IDs are independently sampled 32-byte values from a cryptographically secure random number generator. The ID byte value is encoded as Bitcoin/Solana-alphabet base58 for display and JSON. A decoder MUST yield exactly 32 bytes; the all-zero value is invalid. IDs MUST NOT be generated from paths, timestamps, content hashes, or wallet addresses. A collision MUST be rejected and retried; records MUST NOT be merged. Version IDs are unique within an Origin; implementations SHOULD also reject a known global duplicate. A ManifestID is not a hash; the signed manifest hash is a separate deterministic commitment.

Actor IDs are stable pseudonymous identifiers, represented the same way. They are not signing keys. An actor may rotate signing keys without changing its Actor ID; the authorization service or credential MUST establish that relationship.

## 3. Content fingerprint

`content_hash` is lowercase hexadecimal SHA-256 over the exact file bytes, with no metadata stripping or media decoding. Implementations MUST support streaming input. Empty content is valid and hashes to `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

A perceptual fingerprint MAY be stored as a non-authoritative discovery hint. It MUST NOT replace SHA-256 for integrity checks, asset identity, or version equivalence. Equal content hashes do not merge two separately registered Origins.

## 4. Manifest and signatures

### 4.1 Signed core

The signed core is a JSON object matching `manifest-schema.json`. It contains protocol/version, origin, version, and manifest IDs, nullable primary parent, exact-byte content hash and size, media type, actor and identity mode, action and relationship, UTC claim time, optional parent manifest hash, source references, and optional application/model claims.

The JSON object MUST have no duplicate keys and MUST be serialized with RFC 8785 JSON Canonicalization Scheme (JCS) to UTF-8. No additional Unicode normalization is performed. Numbers MUST be integers from 0 through 9,007,199,254,740,991; floating-point values are forbidden. `created_at` MUST be an RFC 3339 UTC timestamp ending in `Z`; implementations MUST preserve the supplied timestamp string and MUST NOT use it as authoritative ordering.

### 4.2 Hash and signature envelope

Let `C` be the JCS byte sequence of the signed core.

```text
manifest_hash = SHA256(UTF8("ORIGINCHAIN:MANIFEST:V1\0") || C)
signature_message = UTF8("ORIGINCHAIN:MANIFEST-SIGNATURE:V1\0") || manifest_hash
signature = Ed25519.Sign(private_key, signature_message)
```

`manifest_hash` is lowercase hexadecimal and is distinct from the random `manifest_id` in the core. The detached envelope records the algorithm (`Ed25519`), public key, and base58 signature. The envelope, Solana transaction reference, storage URI, and credentials are excluded from the core hash. The verifying key MUST be authorized for the claimed actor under the relevant identity/asset policy.

### 4.3 Application claims

An optional application claim can name application and version, and optionally a model and version. It is a signed assertion by the manifest signer. It does not prove that the application or model produced the bytes. Stronger attestation evidence must be separately referenced and independently validated.

## 5. Registration and version graph

Registration is an explicit publisher action. It creates a new Origin and one root Version whose parent is null. An independent original uses `action_type=create` and `relationship=root`. A newly registered derivative or composition also has a null parent in its new Origin, uses `relationship=derivative` or `composition`, and cites its source Version(s); thus `parent_version_id=null` identifies the root node, while `relationship` describes how that root relates to other Origins. Every null-parent Version has `parent_manifest_hash=null`; a continuation has a non-null parent and matching parent manifest hash.

Every later Version has a distinct Version ID, the same Origin ID, one existing primary parent Version in that Origin, a content hash different from its parent's hash, a signed manifest, and an authorized actor. The manifest's `parent_manifest_hash` is required and MUST equal the parent's manifest hash. If output bytes equal the parent bytes, record an event if needed; do not create a new Version. Immutable records cannot be overwritten, reparented, or silently deleted. Concurrent children of the same parent are valid branches. On-chain sequence numbers are ordering hints; IDs and parent links define identity and ancestry.

For a modified continuation of an asset, keep the Origin ID and point to the prior Version. For a derivative treated as a separate asset, mint a new Origin ID and cite its source asset/version. A new composition may cite multiple source versions; it has no primary parent in its new Origin. A composition that continues one existing Origin has one primary parent and may cite additional sources. Source references do not grant editing rights.

The chain program MUST check signer authorization, parent existence, Origin match, uniqueness, and grant expiry/revocation. Backend validation is useful but never substitutes for on-chain checks.

## 6. Operation semantics

### 6.1 Operations that preserve the version

Send, receive, copy, move, rename, open, and unchanged download preserve the existing Origin and Version. They may create an Event record when explicitly reported, but no new Version. Exporting or importing a portable object also preserves identity and version.

### 6.2 Operations that create a version

An edit, AI modification, transform/re-encode, or composition that yields different bytes creates a new Version (continuation) or a new Origin with source references (derivative/composition). The resulting file must be hashed again. A user-declared edit that results in identical bytes may be recorded as an event but cannot create a distinct content Version in v1.

### 6.3 Event model and evidence

An event has Event ID, actor, action, claimed time, optional device/application, optional input and output hashes, evidence level, and optional resulting Version ID. Events are append-only claims and can be stored off-chain; only a commitment or selected state is required on-chain. Event evidence levels are:

1. `user_declaration`
2. `application_signed`
3. `runtime_observed`
4. `hardware_attested`
5. `chain_committed`

These levels describe evidence present, not a universal ranking of truth. A chain commitment proves inclusion of a commitment, not the event's real-world cause. A runtime may miss file changes and MUST expose unresolved, deferred, failed, and reconciled states.

## 7. Identity and privacy

`identity_mode` is one of `anonymous`, `pseudonymous`, or `credentialed`. These values describe the publisher's disclosure mode only; they do not attest to real-world identity. Private identity evidence and media content MUST remain off-chain. Version commitments are public in the first implementation. Users MUST explicitly opt to register content and be told that public hashes can be compared with known files. The initial protocol does not promise private registration.

Runtime monitoring MUST be opt-in, show active policies, support exclusions, and avoid silent media upload. Hashing and sync MUST not block ordinary file saves.

## 8. On-chain record and independent verification

The first Solana program stores independently verifiable per-version records and authorization state. At minimum the commitment covers Origin ID, Version ID, parent ID, content hash, manifest hash, actor, action type, sequence, and claimed time. The implementation MUST document exact account encoding, PDA seeds, emitted events, and authorization rules before deployment. Media is never stored on-chain.

An independent verifier MUST be able to retrieve the signed core/envelope, recompute exact file bytes' SHA-256, canonicalize the core, recompute the manifest hash, validate the Ed25519 signature, and check the referenced chain commitment and version relationships.

Outcomes:

- `verified`: file hash, manifest signature, authorization evidence, and chain commitment agree.
- `unverified`: no matching trusted registration/commitment is found.
- `tampered`: a claimed known Version conflicts with its committed content or manifest hash, or its signature fails.
- `incomplete`: required evidence or chain/index data is unavailable, so no stronger result is justified.

## 9. Compatibility and extensions

The protocol identifier is `originchain`; the initial protocol version is `1.0.0`. Breaking changes to byte serialization, identifier rules, hash/signature preimages, or parent semantics require a new major version. Additive optional fields require a minor version and an updated schema/fixture set. Implementations MUST reject unknown core fields for the current schema unless they explicitly support the declared newer protocol version. Extension data that must not affect v1 signatures belongs in a detached envelope.

The `media_type` is a lower-case type/subtype without parameters. New media types do not change core protocol semantics. Application-specific claims use the optional `application_claim`; new extension registries require a later specification.

## 10. Conformance requirements

An implementation conforms to protocol v1 only if it:

- decodes IDs to exactly 32 non-zero bytes;
- hashes exact bytes with SHA-256;
- emits RFC 8785 canonical JSON and the specified domain-separated hash/signature preimages;
- rejects invalid signatures and unauthorized actor keys;
- enforces root and parent/Origin rules;
- preserves identity through transmission-neutral operations;
- permits concurrent branches without reparenting history;
- distinguishes file integrity from authorship and application claims;
- passes every fixture in `test-vectors/` byte-for-byte.

## 11. Normative fixture scenarios

The fixture set includes content-hash known answers and canonical manifest/signature inputs. Implementations must add cross-language fixtures for: original image/video registration; copy/move/transfer without a new Version; human edit; AI modification with an untrusted model claim; format conversion; two independent children of one parent; derivative with multiple sources; duplicate content registered as separate Origins; malformed IDs; and signature/content tampering.

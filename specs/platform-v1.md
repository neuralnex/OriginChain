# OriginChain Hosted Platform v1

Status: product direction and architecture requirements.

## Product model

OriginChain has two cooperating products:

1. **Open-source adapters:** native OS and application connectors that users or developers can build by cloning the repository, inspect, modify, or self-host. Adapters observe only authorized media surfaces, create local provenance records, and connect through a documented local/runtime API.
2. **OriginChain Platform:** the hosted web service where users organize assets, collaborate with people and teams, share media and files, inspect provenance, and request chain verification or registration.

The hosted platform is the convenient default. The adapters remain useful without it and may connect to another compatible service. Keep the core protocol and local records portable so a user can leave the hosted service without losing their provenance history.

## User experience

- A user or team can create a workspace, add media/files, invite collaborators, and set owner, editor, and viewer permissions.
- OriginChain stores shareable off-chain file objects and signed manifests. It stores only hashes, identity/version commitments, and authorization state on Solana.
- Sharing unchanged bytes preserves the Origin ID and Version ID. Editing creates a child version or an independently declared branch.
- A receiver can open a shared item, verify its bytes and manifest, and continue a permitted collaboration branch.
- Users can choose private workspace, specific collaborators, or public sharing. Public Solana commitments reveal hashes and cannot be deleted from the chain; this must be clear before registration.
- Files outside the initial image/video UX remain supported by the media-agnostic protocol and open adapter interfaces.

## Open adapter contract

Adapters are open-source components in the OriginChain repository. Contributors can clone the repository, build an adapter, or maintain a fork. The platform must document a versioned adapter API for:

- media create/import/change/transfer observations;
- user permission and coverage reporting;
- local identity and signed manifest creation;
- portable provenance import/export;
- authenticated sync to a selected OriginChain-compatible endpoint;
- user-controlled chain registration requests;
- capability and protocol version negotiation.

Adapters MUST expose what they observed and what they could not observe. They MUST NOT claim global device coverage, silently upload media, or silently publish public chain commitments. The default hosted endpoint must be replaceable with a self-hosted endpoint.

## Founder-funded launch

The initial hosted platform is free to users. The founder funds the initial service operation, including configured storage, bandwidth, indexing, and platform-sponsored Solana registration costs. This product policy is not a promise of unlimited capacity: launch settings must include published, configurable fair-use ceilings and abuse controls before onboarding beyond a private beta. Do not introduce user billing without a deliberate product-policy change.

Sponsored registration keeps the provenance signer separate from the transaction fee/rent payer:

- the user signs the manifest and authorizes the registration;
- the platform sponsor pays the Solana fee and account rent from an isolated, budgeted sponsor key;
- the program records the user as creator/actor, never as the sponsor;
- the backend authenticates the user, applies rate and budget limits, assembles the transaction, and obtains sponsor approval through a protected signer/KMS boundary;
- the platform reports the sponsorship clearly and returns the transaction signature.

The sponsor must have a per-user and global daily budget, rate limits, duplicate/idempotency protection, media size and retention limits, and an emergency pause. Sponsored registration must remain an explicit user action because a public hash is permanent even when hosting is free.

## Data and trust boundaries

- Media bytes live off-chain in an object store. Access requires workspace authorization and short-lived, scoped download links.
- Encrypt stored objects and transport; define retention, deletion, backup, and incident-recovery rules before public launch.
- Deleting a hosted object does not delete the public Solana commitment or copies already shared with other users.
- A platform account or collaboration permission is not an on-chain identity credential. Keep user account authorization separate from wallet/device signatures.
- Platform collaboration claims describe who had access or submitted an event; they do not establish legal authorship or truthful application behavior.
- Self-hosted adapters and independent verifiers must be able to validate the protocol without trusting the OriginChain server.

## Delivery gates

1. Adapter interface and endpoint configuration are documented.
2. Linux runtime creates and verifies local identities without a hosted account.
3. Hosted account, workspace, permission, and encrypted object-sharing services exist.
4. Runtime sync is resumable and idempotent, with explicit per-workspace policy.
5. A sponsored devnet transaction preserves user creator identity while the service pays rent and fee.
6. Budget, quota, privacy, deletion, and emergency-pause controls work before inviting external beta users.
7. macOS/Windows adapters and native Android/iOS capture/share apps connect through the same versioned contract, respecting their individual platform permissions.

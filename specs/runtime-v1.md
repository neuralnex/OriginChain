# OriginChain Device Runtime v1

Status: product and engineering scope for the first device runtime.

## Product promise

OriginChain assigns a persistent identity to each image or video that an OriginChain-aware capture flow creates or that the user imports into an enabled OriginChain surface. The runtime fingerprints exact file bytes, keeps a local provenance record, and can match the file to a previously registered version. It must distinguish an identity record from proof of authorship.

The runtime does not claim that an unintegrated app or another operating system has observed a file. Operating systems restrict background services and access to other apps' private files. Coverage is visible to users and limited to enabled folders, libraries, capture apps, share/import flows, and app integrations.

## Identity lifecycle

1. **Capture or creation:** an integrated OriginChain camera/editor creates an Origin ID and root Version ID before or as it saves the output.
2. **Observed file:** a permitted runtime detects a stable image/video file, hashes its exact bytes, then checks the local index and configured OriginChain registry.
3. **Known bytes:** if exact bytes match a registered version, the runtime attaches that existing identity and version. Matching bytes do not prove that the current person created them.
4. **Unknown bytes:** the runtime creates a local Origin ID and root Version ID with an `observed_import` event. It records that attribution is unknown unless the user supplies a signed claim. It does not create a false parent relationship.
5. **Content change:** a changed fingerprint is a candidate new version only when the user or an integrated application identifies the parent and operation. Otherwise the runtime records an unresolved change.
6. **Transfer:** identity travels in a signed portable provenance package or through a registry lookup. Copying or transmitting unchanged bytes creates no new version. Sidecars and filesystem metadata are conveniences, not the only source of identity.
7. **Chain registration:** the default is local identity with explicit user-controlled chain registration. Public commitments disclose content hashes; the hosted platform may sponsor transaction costs, but the runtime must not silently publish every personal photo.

Local IDs do not automatically resolve on another device. Cross-device continuity requires a carried signed manifest/package or a previously published registry commitment.

## Runtime responsibilities

- Observe only user-approved locations and media libraries.
- Debounce incomplete writes and hash a file only after it is stable.
- Use streaming SHA-256 and never block the application that saved the file.
- Persist device identity, file mappings, signed manifests, event queue, coverage policy, and reconciliation cursor in local storage.
- Keep a clear evidence state: `local_only`, `matched_registered_version`, `pending_user_review`, `pending_chain_registration`, `registered`, `unresolved`, or `failed`.
- Recover after missed notifications by reconciling an explicitly covered library or directory.
- Keep media bytes on the device unless the user explicitly chooses an upload destination.
- Provide per-location exclusions, pause controls, delete/export controls, and an observable record of what was scanned and published.
- Never infer authorship, AI use, or edit history from a filename, timestamp, perceptual match, or filesystem event alone.

## Platform coverage model

| Platform | First integration surface | Coverage and constraint |
| --- | --- | --- |
| Linux | Rust user service watching user-selected folders; portal/share integration later | `inotify` watches directories, is non-recursive, and can miss overflow or remote-filesystem events; reconcile watched trees. Broader `fanotify` coverage requires stronger permissions and has its own gaps. |
| macOS | Menu bar app with user-approved folders, Photos import, Finder/share action | Use user-granted access and directory change APIs. A general third-party app cannot silently monitor every other app's private data. |
| Windows | User-mode tray service watching opted-in folders, Explorer/share action | `ReadDirectoryChangesW` reports changes within watched directory trees; buffer overflow requires a rescan. Volume-wide tracking is a separate, more privileged integration. |
| Android | Native companion app using MediaStore and Android Sharesheet; OriginChain camera/import | Media access is permission-gated and may be limited to selected photos. Other apps' private storage is not visible to the runtime. |
| iOS/iPadOS | OriginChain camera/import app, PhotoKit library observer, share extension, File Provider for OriginChain-managed files | PhotoKit requires authorization and may grant only selected assets. Background execution is system-controlled; there is no third-party filesystem daemon with unrestricted access. |

Platform adapters share the same protocol core and local event model, but the native permission and event APIs remain platform-specific. A single always-on Rust process is not the mobile architecture: iOS and Android use native app/extension lifecycles with a shared Rust cryptographic core where practical.

## Delivery order

### R1 — Runtime protocol and local records

Specify local event states, device key lifecycle, identity persistence, exclusions, stable-write detection, offline behavior, and reconciliation. Do not publish automatically.

#### Local records

The runtime database is a rebuildable index, while signed sidecars are portable local evidence. Store no media bytes in SQLite. A local asset record contains `origin_id`, `root_version_id`, current known `content_hash`, `media_type`, `size_bytes`, `first_observed_at`, `last_observed_at`, `evidence_state`, and a reference to its signed manifest. A path mapping contains a normalized local path, file identity where the platform exposes one, last observed fingerprint, and the associated Origin/Version IDs. Paths are device-local hints and never protocol identifiers.

The v1 Linux sidecar is `<filename>.originchain.json` and contains the manifest core plus its detached signature envelope. It does not change or embed data into the media bytes. Import verifies the media hash, manifest hash, and signature before adopting the IDs. A missing sidecar or filesystem attribute cannot be treated as evidence that a file has no identity; the runtime may search local/hosted registries when explicitly configured.

#### Events and states

The local append-only event log uses `event_id`, `device_id`, `observed_at`, `event_type`, `evidence_level`, optional `origin_id`/`version_id`, optional before/after hashes, and a result state. Initial event types are `observed_import`, `observed_copy`, `observed_move`, `observed_change`, `manifest_imported`, `registration_requested`, and `reconciled`. `observed_*` describes what the runtime saw; it does not prove which app or person caused it.

Event result states are `queued`, `processing`, `local_only`, `matched_registered_version`, `pending_user_review`, `pending_chain_registration`, `registered`, `unresolved`, and `failed`. A write-in-progress is not an event result: the runtime waits for size and modification time to remain stable across consecutive checks, then hashes. Debounce intervals are configurable and the service never holds a file open beyond the hashing read.

#### Device key and permissions

Each installation creates one Ed25519 device key for local manifest/event signatures. Linux v1 stores the raw key under the user's state directory with owner-only directory/file permissions; later platform adapters use their OS key store. The key is never uploaded or used to pay Solana fees. Losing the key prevents that installation from signing new local claims but does not invalidate already exported signed manifests. Key rotation creates a new device identity and does not rewrite older signatures.

Watching a root is an explicit user action. Roots and excluded subtrees are stored by canonical local path. Exclusions win over included descendants; paths outside an approved root are never read. Pausing watching prevents new scan/hash operations. Resume always runs reconciliation before announcing the watcher is current. A missing watcher event or overflow must lead to `unresolved`/reconciliation, never a fabricated edit history.

#### Identity collision and copies

Never merge two assets solely because their SHA-256 hashes match. A valid matching sidecar or an explicit user resolution carries identity through a copy. Without either, an exact-hash match is only a candidate match and remains `pending_user_review`; otherwise a new local identity is created. If a tracked path changes bytes while its previous manifest is present, retain the old claim and mark `observed_change` as `pending_user_review`; do not silently overwrite the sidecar or invent a parent/action.

### R2 — Linux vertical slice

Build an opt-in Rust service for user-selected directories, SQLite state, streaming image/video fingerprints, local Origin ID assignment, signed local manifests, pause/exclusion controls, CLI inspection, and restart reconciliation. No chain transaction is needed to prove this local lifecycle. An early CLI implementation now exists at `runtime/daemon`; it must pass the documented Linux lifecycle smoke run before R2 is marked complete.

### R3 — Linux portable identity

Export/import a signed provenance package and verify identity after copying it to another directory or device. Initial OCPO v1 directory-format CLI commands now exist (`export-object`, `verify-object`, `import-object`); complete the manual cross-device smoke run and interoperability review before marking R3 complete. Add explicit wallet-assisted devnet registration from the existing Explorer/API flow.

### R4 — macOS and Windows adapters

Implement native permission onboarding, selected-folder observation, restart recovery, and platform share/file-manager actions. Use native installers and OS key storage; do not add privileged drivers to the first release.

### R5 — Android and iOS companion apps

Implement capture/import/share flows first, then permission-limited library observation. Make partial-access and background limits explicit in coverage status. Do not promise observation of other apps' private storage.

### R6 — Application integrations

Offer SDKs and signed semantic declarations for camera, image, and video applications. An application claim is labeled as an assertion unless independently attested.

### R7 — Hosted collaboration platform

After Linux, desktop, and mobile adapter foundations exist, connect them to hosted workspaces for collaboration and media/file sharing. Preserve the replaceable endpoint and portable identity requirements in `specs/platform-v1.md`.

## Runtime v1 acceptance

- A new image or video in an enabled Linux folder receives a local Origin ID and root Version ID after its bytes stop changing.
- Repeated events for unchanged bytes resolve to the same local version.
- A transfer/copy within the observed area preserves identity and does not create a version.
- A modification becomes a reviewable candidate and does not claim an editor or parent without evidence.
- A killed/restarted service reconciles its selected locations without duplicating identities.
- Excluded folders remain unobserved; pausing monitoring stops new scans.
- Offline records remain local and queue for later user-authorized sync.
- Export/import preserves the signed manifest and verifies the exact file hash.
- Chain registration requires a separate, understandable user action; the hosted platform may pay the fee and account rent through a budgeted sponsor.

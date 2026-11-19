# OriginChain Portable Object (OCPO) v1

Status: initial directory-format specification for the Linux runtime milestone.

An OCPO is a directory with the `.ocp` suffix. It transports exact media bytes and a signed OriginChain manifest together. Import and export preserve the existing Origin ID and Version ID; they do not create provenance versions. OCPO v1 supports image and video content.

## Required entries

```text
asset.ocp/
  format.json
  content.bin
  manifest.json
```

`format.json` is UTF-8 JSON containing `format: "originchain-portable-object"`, `format_version: "1"`, `content_file: "content.bin"`, and `manifest_file: "manifest.json"`.

`content.bin` contains the exact original file bytes. `manifest.json` contains the signed sidecar envelope: `manifest` plus `signature`. The manifest commits to SHA-256 of `content.bin`, its exact byte length, MIME type, Origin ID, Version ID, and manifest ID. The signature verification rules are defined in `specs/protocol-v1.md` and the signed manifest schema.

## Validation requirements

- Require the three fixed entries to be regular files; reject symlinks and non-file entries.
- Reject unsupported format versions, malformed identifiers, unsupported hash algorithms, content hash or size mismatch, unsupported media type, and invalid signatures.
- Never follow manifest-supplied paths. V1 uses fixed names and does not extract archives.
- Verify the object before importing. Never overwrite existing media or sidecars.
- Copying/importing preserves the signed manifest and identity. A destination path's extension must match its declared MIME type.
- An OCPO is evidence that a signing key signed these claims and that the content matches them. It does not independently prove authorship or capture time.

V1 directory packages are intentionally simple to inspect and copy. A compressed/archive transport can be specified later with explicit size limits, compression-bomb defenses, and traversal handling.

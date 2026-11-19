# OriginChain Linux Runtime (early development)

This opt-in user service watches only directories you add. It fingerprints supported image and video files locally, assigns a local Origin ID and root Version ID, and writes a signed `<filename>.originchain.json` sidecar. It does not upload media, contact Solana, or publish identities. A detected edit is marked for review; the runtime does not infer an editor or create a child version.

The sidecar is a local portability mechanism. Treat it like provenance metadata and keep it with the media file when copying the file. Deleting the sidecar does not delete the media, but another device will not automatically know its Origin ID without that sidecar or a future registry lookup.

## Build and run

From the repository root, with the Rust toolchain installed:

```sh
cargo build -p originchain-runtime
mkdir -p "$HOME/Pictures/OriginChain-watch"
target/debug/originchain-runtime init "$HOME/.local/share/originchain"
target/debug/originchain-runtime add-folder "$HOME/.local/share/originchain" "$HOME/Pictures/OriginChain-watch"
target/debug/originchain-runtime status "$HOME/.local/share/originchain"
target/debug/originchain-runtime watch "$HOME/.local/share/originchain"
```

Keep `watch` running in a terminal for this first development build. Press Ctrl-C to stop it. Restarting it performs a reconciliation scan of configured roots.

In another terminal:

```sh
target/debug/originchain-runtime list "$HOME/.local/share/originchain"
target/debug/originchain-runtime pause "$HOME/.local/share/originchain"
target/debug/originchain-runtime resume "$HOME/.local/share/originchain"
target/debug/originchain-runtime exclude "$HOME/.local/share/originchain" "$HOME/Pictures/OriginChain-watch/private"
```

`exclude` and `include` accept existing directories. Exclusions apply recursively. The Linux MVP recognizes image and video extensions through MIME type detection. Watch only folders where adding sidecars is acceptable; a future UI will make review and sidecar placement more flexible.

## Current limitations

- Early development; the CLI and local database are not yet a polished installer or desktop service.
- A filesystem change is evidence that bytes changed, not proof of who or what changed them.
- Changed files require a user/application workflow to approve and create a new version; that workflow is not implemented yet.
- Signed package export/import and cross-device identity recovery are the next milestone.
- The watcher uses recursive notifications plus restart reconciliation; notification overflow handling and platform-specific coverage reporting still need work.
- Only the local Linux service is implemented. No chain registration or hosted synchronization occurs.

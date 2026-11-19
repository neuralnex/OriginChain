import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  canonicalJson,
  contentHashBytes,
  contentHashStream,
  decodeBase58,
  manifestHash,
  newId,
  parseManifestJson,
  signManifest,
  validateId,
  validateManifestCore,
  verifyManifestSignature,
  ManifestError,
} from "../dist/index.js";

const vector = JSON.parse(readFileSync(new URL("../../../specs/test-vectors/manifest-root-v1.json", import.meta.url), "utf8"));
const core = vector.core;

test("matches protocol v1 canonical manifest and signature vector", () => {
  assert.equal(contentHashBytes(new TextEncoder().encode(vector.content_bytes_utf8)), vector.content_sha256);
  assert.equal(new TextDecoder().decode(canonicalJson(core)), vector.canonical_core_utf8);
  assert.equal(manifestHash(core), vector.manifest_hash);
  const envelope = {
    algorithm: vector.signature_algorithm,
    public_key: vector.test_public_key_base58,
    signature: vector.signature_base58,
  };
  assert.equal(verifyManifestSignature(core, envelope), true);
  assert.equal(verifyManifestSignature(core, envelope, new Set([envelope.public_key])), true);
  assert.equal(verifyManifestSignature(core, envelope, new Set([newId()])), false);
  assert.equal(verifyManifestSignature({ ...core, content_hash: "0".repeat(64) }, envelope), false);
});

test("produces the same Ed25519 envelope as the Python/OpenSSL vector", () => {
  const seed = Uint8Array.from({ length: 32 }, (_, index) => index);
  assert.deepEqual(signManifest(core, seed), {
    algorithm: "Ed25519",
    public_key: vector.test_public_key_base58,
    signature: vector.signature_base58,
  });
});

test("validates IDs and hashes streams", async () => {
  const id = newId();
  assert.equal(validateId(id), id);
  assert.equal(decodeBase58(id).length, 32);
  assert.throws(() => validateId("1".repeat(32)), ManifestError);
  async function* chunks() {
    yield new TextEncoder().encode("Origin");
    yield new TextEncoder().encode("Chain");
  }
  assert.equal(await contentHashStream(chunks()), contentHashBytes(new TextEncoder().encode("OriginChain")));
});

test("rejects duplicate JSON keys after escape decoding", () => {
  assert.throws(() => parseManifestJson('{"protocol":"originchain","protocol":"originchain"}'), ManifestError);
  assert.throws(() => parseManifestJson('{"origin_id":"a","\\u006frigin_id":"b"}'), ManifestError);
});

test("uses RFC 8785 UTF-16 property ordering and rejects non-integers", () => {
  assert.equal(new TextDecoder().decode(canonicalJson({ "\ue000": 1, "\u{10000}": 2 })), '{"𐀀":2,"":1}');
  assert.throws(() => canonicalJson({ count: 1.25 }), ManifestError);
  assert.throws(() => canonicalJson({ bad: "\ud800" }), ManifestError);
  assert.throws(() => validateManifestCore({ ...core, created_at: "2026-02-30T03:04:05Z" }), ManifestError);
});

test("enforces version parent rules and permits sibling branches", () => {
  const child = {
    ...core,
    version_id: newId(),
    manifest_id: newId(),
    parent_version_id: core.version_id,
    parent_manifest_hash: manifestHash(core),
    content_hash: contentHashBytes(new TextEncoder().encode("edited image bytes")),
    size_bytes: new TextEncoder().encode("edited image bytes").length,
    action_type: "edit",
    relationship: "continuation",
    created_at: "2026-01-02T03:05:05Z",
  };
  validateManifestCore(child, core);
  validateManifestCore({ ...child, version_id: newId(), manifest_id: newId() }, core);
  assert.throws(() => validateManifestCore({ ...child, parent_version_id: newId() }, core), ManifestError);
  assert.throws(() => validateManifestCore({ ...child, content_hash: core.content_hash }, core), ManifestError);
});

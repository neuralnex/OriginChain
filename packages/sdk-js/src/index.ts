import {
  createHash,
  createPrivateKey,
  createPublicKey,
  randomBytes,
  sign as ed25519Sign,
  verify as ed25519Verify,
} from "node:crypto";
import { createReadStream } from "node:fs";

const BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
const MANIFEST_DOMAIN = new TextEncoder().encode("ORIGINCHAIN:MANIFEST:V1\0");
const SIGNATURE_DOMAIN = new TextEncoder().encode("ORIGINCHAIN:MANIFEST-SIGNATURE:V1\0");
const MAX_SAFE = Number.MAX_SAFE_INTEGER;
const HASH_RE = /^[0-9a-f]{64}$/;
const MEDIA_TYPE_RE = /^[a-z0-9!#$&^_.+-]+\/[a-z0-9!#$&^_.+-]+$/;
const TIME_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,9})?Z$/;

export type ActorType = "person" | "application" | "device" | "organization" | "unknown";
export type IdentityMode = "anonymous" | "pseudonymous" | "credentialed";
export type ActionType = "create" | "edit" | "ai_modify" | "transform" | "compose";
export type Relationship = "root" | "continuation" | "derivative" | "composition";

export interface SourceReference {
  origin_id: string;
  version_id: string;
  role: string;
}

export interface ManifestCore {
  protocol: "originchain";
  protocol_version: "1.0.0";
  origin_id: string;
  version_id: string;
  manifest_id: string;
  parent_version_id: string | null;
  content_hash: string;
  hash_algorithm: "sha-256";
  media_type: string;
  size_bytes: number;
  actor: { actor_id: string; actor_type: ActorType };
  identity_mode: IdentityMode;
  action_type: ActionType;
  relationship: Relationship;
  created_at: string;
  parent_manifest_hash?: string | null;
  sources?: SourceReference[];
  application_claim?: {
    application_id: string;
    application_version: string;
    model_id?: string;
    model_version?: string;
  };
}

export interface SignatureEnvelope {
  algorithm: "Ed25519";
  public_key: string;
  signature: string;
  message_encoding?: "binary-v1" | "utf8-hex-v1";
}

export class ManifestError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ManifestError";
  }
}

function concat(...parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((size, part) => size + part.length, 0);
  const result = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    result.set(part, offset);
    offset += part.length;
  }
  return result;
}

function rejectUnpairedSurrogates(value: string): void {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      if (!(next >= 0xdc00 && next <= 0xdfff)) throw new ManifestError("unpaired Unicode surrogate");
      index += 1;
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      throw new ManifestError("unpaired Unicode surrogate");
    }
  }
}

function encodeValue(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "string") {
    rejectUnpairedSurrogates(value);
    return JSON.stringify(value);
  }
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value) || value < 0 || value > MAX_SAFE) {
      throw new ManifestError("manifest numbers must be non-negative safe integers");
    }
    return String(value);
  }
  if (Array.isArray(value)) return `[${value.map(encodeValue).join(",")}]`;
  if (typeof value === "object" && value !== undefined) {
    const object = value as Record<string, unknown>;
    if (Object.getPrototypeOf(object) !== Object.prototype && Object.getPrototypeOf(object) !== null) {
      throw new ManifestError("manifest objects must be plain JSON objects");
    }
    const keys = Object.keys(object).sort();
    return `{${keys.map((key) => {
      rejectUnpairedSurrogates(key);
      return `${JSON.stringify(key)}:${encodeValue(object[key])}`;
    }).join(",")}}`;
  }
  throw new ManifestError("unsupported JSON value in manifest");
}

export function canonicalJson(value: object): Uint8Array {
  if (value === null || Array.isArray(value) || typeof value !== "object") {
    throw new ManifestError("manifest core must be an object");
  }
  return new TextEncoder().encode(encodeValue(value as Record<string, unknown>));
}

function assertNoDuplicateJsonKeys(source: string): void {
  let offset = 0;
  const whitespace = () => { while (/\s/.test(source[offset] ?? "")) offset += 1; };
  const readString = (): string => {
    const start = offset;
    if (source[offset] !== '"') throw new ManifestError("expected JSON string");
    offset += 1;
    while (offset < source.length) {
      const character = source[offset++];
      if (character === "\\") {
        offset += 1;
      } else if (character === '"') {
        return JSON.parse(source.slice(start, offset)) as string;
      }
    }
    throw new ManifestError("unterminated JSON string");
  };
  const readValue = (): void => {
    whitespace();
    if (source[offset] === "{") {
      offset += 1;
      whitespace();
      if (source[offset] === "}") { offset += 1; return; }
      const keys = new Set<string>();
      for (;;) {
        whitespace();
        const key = readString();
        if (keys.has(key)) throw new ManifestError(`duplicate JSON object key: ${key}`);
        keys.add(key);
        whitespace();
        if (source[offset++] !== ":") throw new ManifestError("expected colon after JSON key");
        readValue();
        whitespace();
        const delimiter = source[offset++];
        if (delimiter === "}") return;
        if (delimiter !== ",") throw new ManifestError("expected comma or closing brace");
      }
    }
    if (source[offset] === "[") {
      offset += 1;
      whitespace();
      if (source[offset] === "]") { offset += 1; return; }
      for (;;) {
        readValue();
        whitespace();
        const delimiter = source[offset++];
        if (delimiter === "]") return;
        if (delimiter !== ",") throw new ManifestError("expected comma or closing bracket");
      }
    }
    if (source[offset] === '"') { readString(); return; }
    const start = offset;
    while (offset < source.length && !/[\s,\]}]/.test(source[offset])) offset += 1;
    if (start === offset) throw new ManifestError("expected JSON value");
  };

  readValue();
  whitespace();
  if (offset !== source.length) throw new ManifestError("unexpected trailing JSON data");
  JSON.parse(source);
}

export function parseManifestJson(source: string): ManifestCore {
  assertNoDuplicateJsonKeys(source);
  const value: unknown = JSON.parse(source);
  if (value === null || Array.isArray(value) || typeof value !== "object") {
    throw new ManifestError("manifest core must be an object");
  }
  validateManifestCore(value as ManifestCore);
  return value as ManifestCore;
}

export function encodeBase58(bytes: Uint8Array): string {
  let number = 0n;
  for (const byte of bytes) number = number * 256n + BigInt(byte);
  let encoded = "";
  while (number > 0n) {
    const remainder = Number(number % 58n);
    number /= 58n;
    encoded = BASE58[remainder] + encoded;
  }
  let zeroes = 0;
  while (zeroes < bytes.length && bytes[zeroes] === 0) zeroes += 1;
  return "1".repeat(zeroes) + encoded;
}

export function decodeBase58(value: string): Uint8Array {
  if (typeof value !== "string" || value.length === 0) throw new ManifestError("base58 value is empty");
  let number = 0n;
  for (const char of value) {
    const digit = BASE58.indexOf(char);
    if (digit < 0) throw new ManifestError("invalid base58 character");
    number = number * 58n + BigInt(digit);
  }
  const body: number[] = [];
  while (number > 0n) {
    body.push(Number(number & 255n));
    number >>= 8n;
  }
  body.reverse();
  let zeroes = 0;
  while (zeroes < value.length && value[zeroes] === "1") zeroes += 1;
  return new Uint8Array([...new Array<number>(zeroes).fill(0), ...body]);
}

export function validateId(value: string): string {
  const bytes = decodeBase58(value);
  if (bytes.length !== 32 || bytes.every((byte) => byte === 0)) {
    throw new ManifestError("protocol IDs must decode to 32 non-zero bytes");
  }
  return value;
}

export function newId(): string {
  for (;;) {
    const raw = randomBytes(32);
    if (raw.some((byte) => byte !== 0)) return encodeBase58(raw);
  }
}

export function contentHashBytes(data: Uint8Array): string {
  return createHash("sha256").update(data).digest("hex");
}

export async function contentHashStream(stream: AsyncIterable<Uint8Array>): Promise<string> {
  const digest = createHash("sha256");
  for await (const chunk of stream) digest.update(chunk);
  return digest.digest("hex");
}

export async function contentHashFile(path: string): Promise<string> {
  return contentHashStream(createReadStream(path));
}

function requireCondition(condition: unknown, message: string): asserts condition {
  if (!condition) throw new ManifestError(message);
}

export function validateManifestCore(core: ManifestCore, parentCore?: ManifestCore): void {
  requireCondition(core && typeof core === "object" && !Array.isArray(core), "manifest core must be an object");
  const allowed = new Set([
    "protocol", "protocol_version", "origin_id", "version_id", "manifest_id", "parent_version_id",
    "content_hash", "hash_algorithm", "media_type", "size_bytes", "actor", "identity_mode",
    "action_type", "relationship", "created_at", "parent_manifest_hash", "sources", "application_claim",
  ]);
  for (const key of Object.keys(core)) requireCondition(allowed.has(key), `unknown manifest field: ${key}`);
  requireCondition(core.protocol === "originchain" && core.protocol_version === "1.0.0", "unsupported protocol version");
  for (const id of [core.origin_id, core.version_id, core.manifest_id]) validateId(id);
  if (core.parent_version_id !== null) validateId(core.parent_version_id);
  requireCondition(HASH_RE.test(core.content_hash), "content_hash must be lowercase SHA-256 hex");
  requireCondition(core.hash_algorithm === "sha-256", "unsupported content hash algorithm");
  requireCondition(MEDIA_TYPE_RE.test(core.media_type), "media_type must be a lowercase type/subtype");
  requireCondition(Number.isSafeInteger(core.size_bytes) && core.size_bytes >= 0, "invalid size_bytes");
  requireCondition(core.actor && typeof core.actor === "object", "actor is required");
  requireCondition(Object.keys(core.actor).sort().join(",") === "actor_id,actor_type", "actor fields are invalid");
  validateId(core.actor.actor_id);
  requireCondition(["person", "application", "device", "organization", "unknown"].includes(core.actor.actor_type), "invalid actor_type");
  requireCondition(["anonymous", "pseudonymous", "credentialed"].includes(core.identity_mode), "invalid identity_mode");
  requireCondition(["create", "edit", "ai_modify", "transform", "compose"].includes(core.action_type), "invalid action_type");
  requireCondition(["root", "continuation", "derivative", "composition"].includes(core.relationship), "invalid relationship");
  const parsedTime = Date.parse(core.created_at);
  requireCondition(
    TIME_RE.test(core.created_at) && Number.isFinite(parsedTime)
      && new Date(parsedTime).toISOString().slice(0, 19) === core.created_at.slice(0, 19),
    "created_at must be a valid RFC 3339 UTC timestamp",
  );
  const sources = core.sources ?? [];
  requireCondition(Array.isArray(sources), "sources must be an array");
  for (const source of sources) {
    requireCondition(Object.keys(source).sort().join(",") === "origin_id,role,version_id", "source fields are invalid");
    validateId(source.origin_id);
    validateId(source.version_id);
    requireCondition(typeof source.role === "string" && source.role.length >= 1 && source.role.length <= 64, "invalid source role");
  }
  if (core.application_claim !== undefined) {
    const claim = core.application_claim;
    requireCondition(claim !== null && typeof claim === "object" && !Array.isArray(claim), "application_claim must be an object");
    const claimFields = new Set(["application_id", "application_version", "model_id", "model_version"]);
    for (const key of Object.keys(claim)) requireCondition(claimFields.has(key), `unknown application_claim field: ${key}`);
    requireCondition(typeof claim.application_id === "string" && claim.application_id.length >= 1 && claim.application_id.length <= 128, "invalid application_id");
    requireCondition(typeof claim.application_version === "string" && claim.application_version.length >= 1 && claim.application_version.length <= 64, "invalid application_version");
    if (claim.model_id !== undefined) requireCondition(typeof claim.model_id === "string" && claim.model_id.length >= 1 && claim.model_id.length <= 256, "invalid model_id");
    if (claim.model_version !== undefined) requireCondition(typeof claim.model_version === "string" && claim.model_version.length >= 1 && claim.model_version.length <= 128, "invalid model_version");
  }
  if (core.parent_manifest_hash !== undefined && core.parent_manifest_hash !== null) {
    requireCondition(HASH_RE.test(core.parent_manifest_hash), "invalid parent_manifest_hash");
  }
  if (core.parent_version_id === null) {
    requireCondition(core.parent_manifest_hash === undefined || core.parent_manifest_hash === null, "root manifest must not have a parent manifest hash");
    if (core.relationship === "root") {
      requireCondition(core.action_type === "create" && sources.length === 0, "independent root must be a source-free create");
    } else if (core.relationship === "derivative") {
      requireCondition(sources.length >= 1, "root derivative must cite a source");
    } else {
      requireCondition(core.relationship === "composition" && sources.length >= 2, "root composition must cite at least two sources");
    }
  } else {
    requireCondition(typeof core.parent_manifest_hash === "string", "non-root manifest must include parent_manifest_hash");
    requireCondition(["continuation", "composition"].includes(core.relationship), "child must be a continuation or composition");
    if (parentCore) {
      requireCondition(parentCore.origin_id === core.origin_id, "parent must belong to the same Origin");
      requireCondition(parentCore.version_id === core.parent_version_id, "parent_version_id does not match parent");
      requireCondition(manifestHash(parentCore) === core.parent_manifest_hash, "parent manifest hash does not match parent");
      requireCondition(parentCore.content_hash !== core.content_hash, "new Version must have different content bytes");
    }
  }
}

export function manifestHash(core: ManifestCore): string {
  validateManifestCore(core);
  return createHash("sha256").update(concat(MANIFEST_DOMAIN, canonicalJson(core))).digest("hex");
}

function signatureMessage(core: ManifestCore, encoding: SignatureEnvelope["message_encoding"] = "binary-v1"): Uint8Array {
  const digest = manifestHash(core);
  if (encoding === "utf8-hex-v1") {
    return new TextEncoder().encode(`ORIGINCHAIN:MANIFEST-SIGNATURE:V1:UTF8-HEX:${digest}`);
  }
  return concat(SIGNATURE_DOMAIN, Uint8Array.from(BufferFromHex(digest)));
}

function BufferFromHex(value: string): number[] {
  const result: number[] = [];
  for (let index = 0; index < value.length; index += 2) result.push(Number.parseInt(value.slice(index, index + 2), 16));
  return result;
}

export function signManifest(core: ManifestCore, privateSeed: Uint8Array): SignatureEnvelope {
  if (privateSeed.length !== 32) throw new ManifestError("Ed25519 private key must be a 32-byte seed");
  const pkcs8Prefix = Uint8Array.from([0x30, 0x2e, 0x02, 0x01, 0x00, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x04, 0x22, 0x04, 0x20]);
  const privateKey = createPrivateKey({ key: concat(pkcs8Prefix, privateSeed), format: "der", type: "pkcs8" });
  const publicKey = createPublicKey(privateKey).export({ type: "spki", format: "der" }).slice(-32);
  const signature = ed25519Sign(null, signatureMessage(core), privateKey);
  return { algorithm: "Ed25519", public_key: encodeBase58(publicKey), signature: encodeBase58(signature) };
}

export function verifyManifestSignature(
  core: ManifestCore,
  envelope: SignatureEnvelope,
  authorizedPublicKeys?: Set<string>,
): boolean {
  try {
    validateManifestCore(core);
    if (envelope.algorithm !== "Ed25519") return false;
    if (authorizedPublicKeys && !authorizedPublicKeys.has(envelope.public_key)) return false;
    const publicBytes = decodeBase58(envelope.public_key);
    const signature = decodeBase58(envelope.signature);
    if (publicBytes.length !== 32 || signature.length !== 64) return false;
    const spkiPrefix = Uint8Array.from([0x30, 0x2a, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x03, 0x21, 0x00]);
    const publicKey = createPublicKey({ key: concat(spkiPrefix, publicBytes), format: "der", type: "spki" });
    return ed25519Verify(null, signatureMessage(core, envelope.message_encoding), publicKey, signature);
  } catch {
    return false;
  }
}

import { Connection, PublicKey, SystemProgram, Transaction, TransactionInstruction } from "@solana/web3.js";
import { Buffer } from "buffer";
import "./style.css";

declare global {
  interface Window { phantom?: { solana?: PhantomProvider }; solana?: PhantomProvider }
}
interface PhantomProvider {
  isPhantom?: boolean;
  publicKey?: PublicKey;
  connect(): Promise<{ publicKey: PublicKey }>;
  signMessage(message: Uint8Array, display?: "utf8"): Promise<{ signature: Uint8Array }>;
  signTransaction(transaction: Transaction): Promise<Transaction>;
}

const PROGRAM_ID = new PublicKey("J6grB9Db5FjKYkGLWf4n81BZg75WEE9KVXbnq5XZBcg1");
const RPC_URL = import.meta.env.VITE_SOLANA_RPC_URL || "https://api.devnet.solana.com";
const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const connection = new Connection(RPC_URL, "confirmed");
const alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
const encoder = new TextEncoder();

function encode58(bytes: Uint8Array): string {
  let n = 0n;
  for (const b of bytes) n = n * 256n + BigInt(b);
  let out = "";
  while (n > 0n) { const r = Number(n % 58n); n /= 58n; out = alphabet[r] + out; }
  let zeros = 0;
  while (zeros < bytes.length && bytes[zeros] === 0) zeros++;
  return "1".repeat(zeros) + out;
}

function randomId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return encode58(bytes);
}

function canonical(value: unknown): string {
  if (value === null || typeof value === "boolean" || typeof value === "string") return JSON.stringify(value) as string;
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value) || value < 0) throw new Error("Manifest numbers must be non-negative safe integers");
    return String(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    return `{${Object.keys(obj).sort().map((key) => `${JSON.stringify(key)}:${canonical(obj[key])}`).join(",")}}`;
  }
  throw new Error("Manifest contains unsupported JSON data");
}

async function sha256(data: Uint8Array): Promise<Uint8Array> {
  const input = data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength) as ArrayBuffer;
  return new Uint8Array(await crypto.subtle.digest("SHA-256", input));
}

function hex(bytes: Uint8Array): string { return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join(""); }
function fromHex(value: string): Uint8Array { return new Uint8Array(value.match(/.{2}/g)!.map((x) => parseInt(x, 16))); }
function concat(...items: Uint8Array[]): Uint8Array {
  const out = new Uint8Array(items.reduce((n, item) => n + item.length, 0));
  let offset = 0; for (const item of items) { out.set(item, offset); offset += item.length; }
  return out;
}
function base64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}
function errorText(error: unknown): string { return error instanceof Error ? error.message : String(error); }

const root = document.querySelector<HTMLDivElement>("#root")!;
root.innerHTML = `
  <main class="shell">
    <header class="topbar"><a class="brand" href="#"><span class="mark">O</span> ORIGINCHAIN</a><span class="network"><i></i> SOLANA DEVNET</span></header>
    <section class="hero"><p class="eyebrow">DIGITAL PROVENANCE, ON CHAIN</p><h1>Give every image<br>and video a history.</h1><p class="intro">Register a file with a signed provenance manifest and a verifiable Solana devnet record.</p></section>
    <section class="panel">
      <div class="panel-head"><div><p class="eyebrow">NEW RECORD</p><h2>Register an original</h2></div><button id="connect" class="connect">Connect Phantom</button></div>
      <div class="wallet-row"><span id="wallet-dot" class="dot"></span><span id="wallet-label">Wallet not connected</span><span class="chain-label">DEVNET</span></div>
      <label class="drop" for="media"><span class="upload-icon">↑</span><strong id="file-title">Choose an image or video</strong><small id="file-meta">PNG, JPEG, WebP, GIF, MP4, MOV and other browser-recognized media · up to 100 MB</small><input id="media" type="file" accept="image/*,video/*"></label>
      <div class="controls"><label class="field-label" for="identity">Publisher identity</label><select id="identity"><option value="anonymous">Anonymous</option><option value="pseudonymous">Pseudonymous</option></select><button id="register" class="primary" disabled>Sign and register <span>→</span></button></div>
      <p class="privacy">The file is sent to your configured API only for integrity verification and is not stored by this MVP. Phantom signs the manifest and transaction.</p>
      <div id="status" class="status" hidden></div>
    </section>
    <footer>OriginChain Protocol v1 <span>•</span> Images + video MVP</footer>
  </main>`;

let provider: PhantomProvider | undefined;
let wallet: PublicKey | undefined;
let selected: File | undefined;
const connectButton = document.querySelector<HTMLButtonElement>("#connect")!;
const registerButton = document.querySelector<HTMLButtonElement>("#register")!;
const fileInput = document.querySelector<HTMLInputElement>("#media")!;
const statusBox = document.querySelector<HTMLDivElement>("#status")!;

function setStatus(message: string, kind: "info" | "success" | "error" = "info", link?: string): void {
  statusBox.hidden = false;
  statusBox.className = `status ${kind}`;
  statusBox.innerHTML = `${message}${link ? ` <a href="${link}" target="_blank" rel="noreferrer">View on Solscan ↗</a>` : ""}`;
}

connectButton.addEventListener("click", async () => {
  try {
    provider = window.phantom?.solana ?? window.solana;
    if (!provider?.isPhantom) throw new Error("Install the Phantom browser extension, then reload this page.");
    const response = await provider.connect();
    wallet = response.publicKey;
    document.querySelector("#wallet-label")!.textContent = wallet.toBase58();
    document.querySelector("#wallet-dot")!.classList.add("online");
    connectButton.textContent = "Wallet connected";
    registerButton.disabled = !selected;
  } catch (error) { setStatus(errorText(error), "error"); }
});

fileInput.addEventListener("change", () => {
  selected = fileInput.files?.[0];
  document.querySelector("#file-title")!.textContent = selected?.name ?? "Choose an image or video";
  document.querySelector("#file-meta")!.textContent = selected ? `${selected.type || "Unknown media type"} · ${(selected.size / 1024 / 1024).toFixed(2)} MB` : "PNG, JPEG, WebP, GIF, MP4, MOV and other browser-recognized media · up to 100 MB";
  registerButton.disabled = !(selected && wallet);
});

registerButton.addEventListener("click", async () => {
  if (!selected || !wallet || !provider) return;
  registerButton.disabled = true;
  registerButton.textContent = "Preparing your record…";
  try {
    if (!(selected.type.startsWith("image/") || selected.type.startsWith("video/"))) throw new Error("Choose a browser-recognized image or video.");
    if (selected.size > 100 * 1024 * 1024) throw new Error("File exceeds the 100 MB MVP upload limit.");
    const fileBytes = new Uint8Array(await selected.arrayBuffer());
    const originId = randomId();
    const versionId = randomId();
    const core = {
      protocol: "originchain", protocol_version: "1.0.0", origin_id: originId, version_id: versionId,
      manifest_id: randomId(), parent_version_id: null, content_hash: hex(await sha256(fileBytes)),
      hash_algorithm: "sha-256", media_type: selected.type.toLowerCase(), size_bytes: selected.size,
      actor: { actor_id: randomId(), actor_type: "person" },
      identity_mode: (document.querySelector<HTMLSelectElement>("#identity")!).value,
      action_type: "create", relationship: "root", created_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    };
    const digest = await sha256(concat(encoder.encode("ORIGINCHAIN:MANIFEST:V1\0"), encoder.encode(canonical(core))));
    const manifestDigest = hex(digest);
    setStatus("Review and approve the manifest signature in Phantom…");
    // Phantom rejects arbitrary byte strings that it can parse as a Solana transaction.
    // This readable, domain-separated UTF-8 form avoids that ambiguity while remaining verifiable.
    const signatureMessage = encoder.encode(`ORIGINCHAIN:MANIFEST-SIGNATURE:V1:UTF8-HEX:${manifestDigest}`);
    const signedMessage = await provider.signMessage(signatureMessage, "utf8");

    const originBytes = decode58(originId);
    const versionBytes = decode58(versionId);
    const [registry] = PublicKey.findProgramAddressSync([encoder.encode("registry")], PROGRAM_ID);
    const [asset] = PublicKey.findProgramAddressSync([encoder.encode("asset"), originBytes], PROGRAM_ID);
    const [version] = PublicKey.findProgramAddressSync([encoder.encode("version"), originBytes, versionBytes], PROGRAM_ID);
    const discriminator = (await sha256(encoder.encode("global:register_asset"))).slice(0, 8);
    const identityEnum = (document.querySelector<HTMLSelectElement>("#identity")!).value === "anonymous" ? 0 : 1;
    const instructionData = concat(discriminator, originBytes, versionBytes, fromHex(core.content_hash), digest, new Uint8Array(32), new Uint8Array([identityEnum]));
    const instruction = new TransactionInstruction({
      programId: PROGRAM_ID,
      keys: [
        { pubkey: registry, isSigner: false, isWritable: false },
        { pubkey: asset, isSigner: false, isWritable: true },
        { pubkey: version, isSigner: false, isWritable: true },
        { pubkey: wallet, isSigner: true, isWritable: true },
        { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
      ],
      data: Buffer.from(instructionData),
    });
    const tx = new Transaction().add(instruction);
    tx.feePayer = wallet;
    tx.recentBlockhash = (await connection.getLatestBlockhash("confirmed")).blockhash;
    setStatus("Review and approve the Solana registration in Phantom…");
    const signedTx = await provider.signTransaction(tx);
    const envelope = { algorithm: "Ed25519", message_encoding: "utf8-hex-v1", public_key: wallet.toBase58(), signature: encode58(signedMessage.signature) };
    const response = await fetch(`${API_URL}/v1/assets`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ manifest: core, signature: envelope, content_base64: base64(fileBytes), transaction_base64: base64(signedTx.serialize()) }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : JSON.stringify(result.detail ?? result));
    const txSignature = result.chain_reference as string;
    setStatus(`Registered ${originId}. Your root version is ${versionId}.`, "success", `https://solscan.io/tx/${txSignature}?cluster=devnet`);
    statusBox.insertAdjacentHTML("beforeend", `<br><small>Origin ID: ${originId}<br>Version ID: ${versionId}</small>`);
  } catch (error) {
    setStatus(errorText(error), "error");
  } finally {
    registerButton.disabled = !(selected && wallet);
    registerButton.innerHTML = 'Sign and register <span>→</span>';
  }
});

function decode58(value: string): Uint8Array {
  let n = 0n;
  for (const char of value) { const digit = alphabet.indexOf(char); if (digit < 0) throw new Error("Invalid base58 ID"); n = n * 58n + BigInt(digit); }
  const bytes: number[] = [];
  while (n > 0n) { bytes.unshift(Number(n & 255n)); n >>= 8n; }
  let zeros = 0; while (zeros < value.length && value[zeros] === "1") zeros++;
  const decoded = new Uint8Array([...new Array(zeros).fill(0), ...bytes]);
  if (decoded.length !== 32) throw new Error("OriginChain ID did not decode to 32 bytes");
  return decoded;
}

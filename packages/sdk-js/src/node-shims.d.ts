declare module "node:crypto" {
  export interface Hash {
    update(data: Uint8Array): Hash;
    digest(encoding: "hex"): string;
  }
  export function createHash(algorithm: string): Hash;
  export interface KeyObject {
    export(options: { type: "spki"; format: "der" }): Uint8Array;
  }
  export function createPrivateKey(options: { key: Uint8Array; format: "der"; type: "pkcs8" }): KeyObject;
  export function createPublicKey(options: { key: Uint8Array; format: "der"; type: "spki" }): KeyObject;
  export function createPublicKey(key: KeyObject): KeyObject;
  export function randomBytes(size: number): Uint8Array;
  export function sign(algorithm: null, data: Uint8Array, key: unknown): Uint8Array;
  export function verify(algorithm: null, data: Uint8Array, key: unknown, signature: Uint8Array): boolean;
}

declare module "node:fs" {
  export function createReadStream(path: string): AsyncIterable<Uint8Array>;
}

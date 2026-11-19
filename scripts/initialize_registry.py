#!/usr/bin/env python3
"""Initialize the OriginChain registry PDA on Solana devnet."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import time
from pathlib import Path

import httpx
from solders.hash import Hash
from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import Transaction


PROGRAM_ID = "J6grB9Db5FjKYkGLWf4n81BZg75WEE9KVXbnq5XZBcg1"
SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"
DEFAULT_RPC = "https://api.devnet.solana.com"


def rpc(client: httpx.Client, url: str, method: str, params: list):
    response = client.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(f"RPC {method} failed: {payload['error'].get('message', 'unknown error')}")
    return payload["result"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keypair", type=Path, default=Path.home() / ".config/solana/id.json")
    parser.add_argument("--rpc-url", default=DEFAULT_RPC)
    args = parser.parse_args()

    if not args.keypair.is_file():
        raise SystemExit(f"Wallet keypair not found: {args.keypair}. Create or select a devnet payer wallet first.")
    secret = json.loads(args.keypair.read_text(encoding="utf-8"))
    payer = Keypair.from_bytes(bytes(secret))
    program_id = Pubkey.from_string(PROGRAM_ID)
    system_program = Pubkey.from_string(SYSTEM_PROGRAM_ID)
    registry, _ = Pubkey.find_program_address([b"registry"], program_id)
    registry_discriminator = hashlib.sha256(b"account:RegistryConfig").digest()[:8]

    with httpx.Client(timeout=30) as client:
        current = rpc(client, args.rpc_url, "getAccountInfo", [str(registry), {"encoding": "base64", "commitment": "confirmed"}])["value"]
        if current is not None:
            current_data = base64.b64decode(current["data"][0], validate=True)
            if current["owner"] != PROGRAM_ID or current_data[:8] != registry_discriminator:
                raise SystemExit("Registry PDA exists but is not owned by the configured OriginChain program.")
            print(f"OriginChain registry already initialized: {registry}")
            return

        blockhash = rpc(client, args.rpc_url, "getLatestBlockhash", [{"commitment": "confirmed"}])["value"]["blockhash"]
        discriminator = hashlib.sha256(b"global:initialize_registry").digest()[:8]
        instruction = Instruction(
            program_id,
            discriminator,
            [
                AccountMeta(registry, is_signer=False, is_writable=True),
                AccountMeta(payer.pubkey(), is_signer=True, is_writable=True),
                AccountMeta(system_program, is_signer=False, is_writable=False),
            ],
        )
        transaction = Transaction.new_signed_with_payer(
            [instruction], payer.pubkey(), [payer], Hash.from_string(blockhash)
        )
        signature = rpc(
            client,
            args.rpc_url,
            "sendTransaction",
            [base64.b64encode(bytes(transaction)).decode("ascii"), {"encoding": "base64", "preflightCommitment": "confirmed"}],
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            statuses = rpc(client, args.rpc_url, "getSignatureStatuses", [[signature], {"searchTransactionHistory": True}])["value"]
            status = statuses[0] if statuses else None
            if status and status.get("err"):
                raise SystemExit(f"Registry initialization failed: {status['err']}")
            if status and status.get("confirmationStatus") in {"confirmed", "finalized"}:
                verify = rpc(client, args.rpc_url, "getAccountInfo", [str(registry), {"encoding": "base64", "commitment": "confirmed"}])["value"]
                if not verify:
                    raise SystemExit("Transaction confirmed, but the registry PDA could not be verified.")
                verify_data = base64.b64decode(verify["data"][0], validate=True)
                if verify["owner"] != PROGRAM_ID or verify_data[:8] != registry_discriminator:
                    raise SystemExit("Transaction confirmed, but registry account type/owner is incorrect.")
                print(f"OriginChain registry initialized: {registry}")
                print(f"Transaction: {signature}")
                return
            time.sleep(0.5)
        raise SystemExit(f"Timed out waiting for confirmation. Transaction: {signature}")


if __name__ == "__main__":
    main()

import base64
import hashlib
import json
import time

import httpx
from originchain_core.manifest import manifest_hash

from ..config import Settings


class ChainError(RuntimeError):
    pass


class ChainAdapter:
    kind: str

    def commit(self, *, operation: str, core: dict, signer: str, transaction_base64: str | None) -> str:
        raise NotImplementedError

    def check(self, *, core: dict, expected_manifest_hash: str, expected_signer: str, reference: str) -> bool | None:
        raise NotImplementedError


class MockChainAdapter(ChainAdapter):
    kind = "mock"

    def commit(self, *, operation: str, core: dict, signer: str, transaction_base64: str | None) -> str:
        material = f"{operation}:{core['origin_id']}:{core['version_id']}:{core['content_hash']}:{manifest_hash(core)}"
        return "mock:" + hashlib.sha256(material.encode()).hexdigest()

    def check(self, *, core: dict, expected_manifest_hash: str, expected_signer: str, reference: str) -> bool | None:
        # Mock records are useful for local API development, but are never chain proof.
        return None


class SolanaRpcAdapter(ChainAdapter):
    kind = "solana"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.program_id = settings.solana_program_id
        self.timeout = settings.request_timeout_seconds

    def _rpc(self, method: str, params: list) -> dict:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.settings.solana_rpc_url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ChainError(f"Solana RPC {method} failed: {exc}") from exc
        if payload.get("error"):
            raise ChainError(f"Solana RPC {method} rejected the request")
        return payload.get("result", {})

    def commit(self, *, operation: str, core: dict, signer: str, transaction_base64: str | None) -> str:
        if not transaction_base64:
            raise ChainError("a wallet-signed transaction_base64 is required for the Solana adapter")
        try:
            transaction = base64.b64decode(transaction_base64, validate=True)
        except ValueError as exc:
            raise ChainError("transaction_base64 is invalid") from exc
        if len(transaction) > 1_232:
            raise ChainError("serialized transaction exceeds Solana packet limit")
        result = self._rpc("sendTransaction", [transaction_base64, {"encoding": "base64", "preflightCommitment": "confirmed", "maxRetries": 3}])
        signature = result.get("result") if isinstance(result, dict) else result
        if not isinstance(signature, str):
            raise ChainError("Solana RPC did not return a transaction signature")
        status = None
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            statuses = self._rpc("getSignatureStatuses", [[signature], {"searchTransactionHistory": True}]).get("value", [])
            status = statuses[0] if statuses else None
            if status and (status.get("err") or status.get("confirmationStatus") in {"confirmed", "finalized"}):
                break
            time.sleep(min(0.5, max(0, deadline - time.monotonic())))
        if not status or status.get("err") or status.get("confirmationStatus") not in {"confirmed", "finalized"}:
            raise ChainError("Solana transaction is not confirmed; retry with the same idempotency key")
        self._check_committed_account(core, signer, signature, operation)
        return signature

    def _account(self, address: str) -> tuple[str, bytes] | None:
        result = self._rpc("getAccountInfo", [address, {"encoding": "base64", "commitment": "confirmed"}]).get("value")
        if not result:
            return None
        try:
            raw = base64.b64decode(result["data"][0], validate=True)
            return result["owner"], raw
        except (KeyError, IndexError, ValueError) as exc:
            raise ChainError("Solana account response was malformed") from exc

    def _pda(self, seeds: list[bytes]) -> str:
        try:
            from solders.pubkey import Pubkey
            program = Pubkey.from_string(self.program_id)
            address, _ = Pubkey.find_program_address(seeds, program)
            return str(address)
        except (ImportError, ValueError) as exc:
            raise ChainError("solders is required to derive OriginChain account addresses") from exc

    @staticmethod
    def _take(data: bytes, offset: int, length: int) -> tuple[bytes, int]:
        end = offset + length
        if end > len(data):
            raise ChainError("OriginChain account data was truncated")
        return data[offset:end], end

    def _decode_asset(self, data: bytes) -> tuple[bytes, bytes, bytes, int]:
        expected = hashlib.sha256(b"account:AssetAccount").digest()[:8]
        if data[:8] != expected:
            raise ChainError("asset PDA contains an unexpected account type")
        origin, pos = self._take(data, 8, 32)
        creator, pos = self._take(data, pos, 32)
        root_version, pos = self._take(data, pos, 32)
        _, pos = self._take(data, pos, 8)  # version_count
        identity_mode, pos = self._take(data, pos, 1)
        if identity_mode[0] > 2:
            raise ChainError("asset account has invalid identity mode")
        return origin, creator, root_version, identity_mode[0]

    def _decode_version(self, data: bytes) -> tuple[bytes, bytes, bytes, bytes, bytes, bytes | None, int]:
        expected = hashlib.sha256(b"account:VersionAccount").digest()[:8]
        if data[:8] != expected:
            raise ChainError("version PDA contains an unexpected account type")
        origin, pos = self._take(data, 8, 32)
        version, pos = self._take(data, pos, 32)
        parent_tag, pos = self._take(data, pos, 1)
        if parent_tag[0] == 1:
            parent, pos = self._take(data, pos, 32)
        elif parent_tag[0] != 0:
            raise ChainError("version account has invalid parent encoding")
        else:
            parent = None
        content_hash, pos = self._take(data, pos, 32)
        manifest_hash, pos = self._take(data, pos, 32)
        _, pos = self._take(data, pos, 32)  # manifest_uri_hash
        actor, pos = self._take(data, pos, 32)
        action, _ = self._take(data, pos, 1)
        return origin, version, content_hash, manifest_hash, actor, parent, action[0]

    def _check_committed_account(self, core: dict, signer: str, signature: str, operation: str) -> None:
        try:
            from solders.pubkey import Pubkey
            from originchain_core.identifiers import decode_id
            origin_id = decode_id(core["origin_id"])
            version_id = decode_id(core["version_id"])
            version_pda = self._pda([b"version", origin_id, version_id])
            version = self._account(version_pda)
            if not version or version[0] != self.program_id:
                raise ChainError("confirmed transaction did not create the expected OriginChain version account")
            account_origin, account_version, content_hash, committed_manifest, actor, parent_id, action = self._decode_version(version[1])
            expected_signer = bytes(Pubkey.from_string(signer))
            action_by_name = {"create": 0, "edit": 1, "ai_modify": 2, "transform": 3, "compose": 4}
            expected_parent = decode_id(core["parent_version_id"]) if core["parent_version_id"] else None
            if (account_origin != origin_id or account_version != version_id or
                    content_hash.hex() != core["content_hash"] or committed_manifest.hex() != manifest_hash(core) or
                    actor != expected_signer or parent_id != expected_parent or action != action_by_name[core["action_type"]]):
                raise ChainError("on-chain version account does not match the signed manifest")
            if operation == "register":
                asset = self._account(self._pda([b"asset", origin_id]))
                if not asset or asset[0] != self.program_id:
                    raise ChainError("confirmed transaction did not create the expected OriginChain asset account")
                asset_origin, creator, root_version, identity_mode = self._decode_asset(asset[1])
                identity_by_name = {"anonymous": 0, "pseudonymous": 1, "credentialed": 2}
                if (asset_origin != origin_id or creator != expected_signer or root_version != version_id or
                        identity_mode != identity_by_name[core["identity_mode"]]):
                    raise ChainError("on-chain asset creator does not match the manifest signer")
        except ImportError as exc:
            raise ChainError("solders dependency is unavailable") from exc

    def check(self, *, core: dict, expected_manifest_hash: str, expected_signer: str, reference: str) -> bool | None:
        try:
            from solders.pubkey import Pubkey
            from originchain_core.identifiers import decode_id
            origin_id = decode_id(core["origin_id"])
            version_id = decode_id(core["version_id"])
            account = self._account(self._pda([b"version", origin_id, version_id]))
            if not account or account[0] != self.program_id:
                return False
            account_origin, account_version, content_hash, committed_manifest, actor, parent_id, action = self._decode_version(account[1])
            from originchain_core.identifiers import decode_id
            expected_parent = decode_id(core["parent_version_id"]) if core["parent_version_id"] else None
            action_by_name = {"create": 0, "edit": 1, "ai_modify": 2, "transform": 3, "compose": 4}
            return (account_origin == origin_id and account_version == version_id and
                    content_hash.hex() == core["content_hash"] and committed_manifest.hex() == expected_manifest_hash and
                    actor == bytes(Pubkey.from_string(expected_signer)) and parent_id == expected_parent and
                    action == action_by_name[core["action_type"]])
        except ImportError as exc:
            raise ChainError("solders dependency is unavailable") from exc


def build_chain_adapter(settings: Settings) -> ChainAdapter:
    mode = settings.chain_adapter.lower()
    if mode == "mock":
        return MockChainAdapter()
    if mode == "solana":
        return SolanaRpcAdapter(settings)
    raise ValueError("CHAIN_ADAPTER must be either 'mock' or 'solana'")

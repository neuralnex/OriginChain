# Security policy

OriginChain is an early protocol specification. It has not been audited and must not be treated as production-ready.

## Security boundaries

- SHA-256 verifies exact bytes, not authorship or truth.
- A valid signature proves control of a signing key, not that an application behaved honestly.
- Filesystem observation can miss changes; runtime claims must include their evidence level.
- Backend/indexer responses must be checkable against Solana and signed manifests.
- Public chain data can reveal that a known file hash was registered. Do not submit sensitive content without understanding this.

## Reporting

Do not publish exploitable vulnerabilities before maintainers have had a chance to respond. Report the affected component, reproduction steps, impact, and any suggested mitigation through the project's private security contact once one is published. No security contact is configured yet.

## Key handling

Never commit signing keys, wallet files, seed phrases, or production credentials. Runtime and publisher key enrollment, rotation, recovery, and revocation remain design work before production use.

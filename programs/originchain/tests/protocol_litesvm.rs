use anchor_lang::{AccountDeserialize, InstructionData, ToAccountMetas};
use litesvm::LiteSVM;
use originchain_program::{
    accounts as program_accounts, id, instruction as program_instruction, ActionType, AssetAccount,
    IdentityMode, VersionAccount,
};
use solana_instruction::Instruction;
use solana_keypair::Keypair;
use solana_message::Message;
use solana_signer::Signer;
use solana_transaction::Transaction;

const PROGRAM_BYTES: &[u8] = include_bytes!("../../../target/deploy/originchain_program.so");

fn test_vm(payer: &Keypair) -> LiteSVM {
    let mut svm = LiteSVM::new();
    svm.add_program(id(), PROGRAM_BYTES)
        .expect("OriginChain program loads into LiteSVM");
    svm.airdrop(&payer.pubkey(), 10_000_000_000).unwrap();
    svm
}

fn send(svm: &mut LiteSVM, payer: &Keypair, instruction: Instruction) -> Result<(), String> {
    let message = Message::new(&[instruction], Some(&payer.pubkey()));
    let transaction = Transaction::new(&[payer], message, svm.latest_blockhash());
    svm.send_transaction(transaction)
        .map(|_| ())
        .map_err(|error| format!("{:?}", error.err))
}

fn initialize_registry(svm: &mut LiteSVM, payer: &Keypair) {
    let (registry, _) = anchor_lang::prelude::Pubkey::find_program_address(&[b"registry"], &id());
    let instruction = Instruction {
        program_id: id(),
        accounts: program_accounts::InitializeRegistry {
            registry,
            authority: payer.pubkey(),
            system_program: anchor_lang::system_program::ID,
        }
        .to_account_metas(None),
        data: program_instruction::InitializeRegistry {}.data(),
    };
    send(svm, payer, instruction).unwrap();
}

#[test]
fn registers_root_and_creates_two_valid_branches() {
    let payer = Keypair::new();
    let mut svm = test_vm(&payer);
    initialize_registry(&mut svm, &payer);

    let origin_id = [1; 32];
    let root_id = [2; 32];
    let (registry, _) = anchor_lang::prelude::Pubkey::find_program_address(&[b"registry"], &id());
    let (asset, _) = anchor_lang::prelude::Pubkey::find_program_address(
        &[b"asset", &origin_id], &id()
    );
    let (root_version, _) = anchor_lang::prelude::Pubkey::find_program_address(
        &[b"version", &origin_id, &root_id], &id()
    );
    let register = Instruction {
        program_id: id(),
        accounts: program_accounts::RegisterAsset {
            registry,
            asset,
            root_version,
            creator: payer.pubkey(),
            system_program: anchor_lang::system_program::ID,
        }
        .to_account_metas(None),
        data: program_instruction::RegisterAsset {
            origin_id,
            root_version_id: root_id,
            content_hash: [3; 32],
            manifest_hash: [4; 32],
            manifest_uri_hash: [0; 32],
            identity_mode: IdentityMode::Pseudonymous,
        }
        .data(),
    };
    send(&mut svm, &payer, register).unwrap();

    let root_account = svm.get_account(&root_version).unwrap();
    let mut root_data = root_account.data.as_slice();
    let root: VersionAccount = VersionAccount::try_deserialize(&mut root_data).unwrap();
    assert_eq!(root.parent_version_id, None);
    assert_eq!(root.action_type, ActionType::Create);
    assert_eq!(root.sequence, 0);

    for (version_id, hash) in [([5; 32], [6; 32]), ([7; 32], [8; 32])] {
        let (version, _) = anchor_lang::prelude::Pubkey::find_program_address(
            &[b"version", &origin_id, &version_id], &id()
        );
        let create = Instruction {
            program_id: id(),
            accounts: program_accounts::CreateVersion {
                registry,
                asset,
                parent_version: root_version,
                version,
                editor_grant: None,
                actor: payer.pubkey(),
                system_program: anchor_lang::system_program::ID,
            }
            .to_account_metas(None),
            data: program_instruction::CreateVersion {
                origin_id,
                version_id,
                parent_version_id: root_id,
                content_hash: hash,
                manifest_hash: [9; 32],
                manifest_uri_hash: [0; 32],
                action_type: ActionType::Edit,
            }
            .data(),
        };
        send(&mut svm, &payer, create).unwrap();
        let child_account = svm.get_account(&version).unwrap();
        let mut child_data = child_account.data.as_slice();
        let child: VersionAccount = VersionAccount::try_deserialize(&mut child_data).unwrap();
        assert_eq!(child.parent_version_id, Some(root_id));
    }

    let asset_account = svm.get_account(&asset).unwrap();
    let mut asset_data = asset_account.data.as_slice();
    let stored_asset: AssetAccount = AssetAccount::try_deserialize(&mut asset_data).unwrap();
    assert_eq!(stored_asset.version_count, 3);
}

#[test]
fn rejects_unchanged_content_and_unauthorized_actor() {
    let payer = Keypair::new();
    let attacker = Keypair::new();
    let mut svm = test_vm(&payer);
    svm.airdrop(&attacker.pubkey(), 1_000_000_000).unwrap();
    initialize_registry(&mut svm, &payer);

    let origin_id = [11; 32];
    let root_id = [12; 32];
    let (registry, _) = anchor_lang::prelude::Pubkey::find_program_address(&[b"registry"], &id());
    let (asset, _) = anchor_lang::prelude::Pubkey::find_program_address(&[b"asset", &origin_id], &id());
    let (root_version, _) = anchor_lang::prelude::Pubkey::find_program_address(&[b"version", &origin_id, &root_id], &id());
    let register = Instruction {
        program_id: id(),
        accounts: program_accounts::RegisterAsset {
            registry,
            asset,
            root_version,
            creator: payer.pubkey(),
            system_program: anchor_lang::system_program::ID,
        }
        .to_account_metas(None),
        data: program_instruction::RegisterAsset {
            origin_id,
            root_version_id: root_id,
            content_hash: [13; 32],
            manifest_hash: [14; 32],
            manifest_uri_hash: [0; 32],
            identity_mode: IdentityMode::Anonymous,
        }
        .data(),
    };
    send(&mut svm, &payer, register).unwrap();

    let make_child = |version_id: [u8; 32], content_hash: [u8; 32], actor: &Keypair| {
        let (version, _) = anchor_lang::prelude::Pubkey::find_program_address(&[b"version", &origin_id, &version_id], &id());
        Instruction {
            program_id: id(),
            accounts: program_accounts::CreateVersion {
                registry,
                asset,
                parent_version: root_version,
                version,
                editor_grant: None,
                actor: actor.pubkey(),
                system_program: anchor_lang::system_program::ID,
            }
            .to_account_metas(None),
            data: program_instruction::CreateVersion {
                origin_id,
                version_id,
                parent_version_id: root_id,
                content_hash,
                manifest_hash: [15; 32],
                manifest_uri_hash: [0; 32],
                action_type: ActionType::Edit,
            }
            .data(),
        }
    };

    let unchanged = make_child([16; 32], [13; 32], &payer);
    assert!(send(&mut svm, &payer, unchanged).is_err());

    let unauthorized = make_child([17; 32], [18; 32], &attacker);
    assert!(send(&mut svm, &attacker, unauthorized).is_err());
}

#[test]
fn editor_can_create_version_until_creator_revokes_grant() {
    let creator = Keypair::new();
    let editor = Keypair::new();
    let mut svm = test_vm(&creator);
    svm.airdrop(&editor.pubkey(), 1_000_000_000).unwrap();
    initialize_registry(&mut svm, &creator);

    let origin_id = [21; 32];
    let root_id = [22; 32];
    let (registry, _) = anchor_lang::prelude::Pubkey::find_program_address(&[b"registry"], &id());
    let (asset, _) = anchor_lang::prelude::Pubkey::find_program_address(&[b"asset", &origin_id], &id());
    let (root_version, _) = anchor_lang::prelude::Pubkey::find_program_address(&[b"version", &origin_id, &root_id], &id());
    let register = Instruction {
        program_id: id(),
        accounts: program_accounts::RegisterAsset {
            registry,
            asset,
            root_version,
            creator: creator.pubkey(),
            system_program: anchor_lang::system_program::ID,
        }
        .to_account_metas(None),
        data: program_instruction::RegisterAsset {
            origin_id,
            root_version_id: root_id,
            content_hash: [23; 32],
            manifest_hash: [24; 32],
            manifest_uri_hash: [0; 32],
            identity_mode: IdentityMode::Pseudonymous,
        }
        .data(),
    };
    send(&mut svm, &creator, register).unwrap();

    let (editor_grant, _) = anchor_lang::prelude::Pubkey::find_program_address(
        &[b"editor", &origin_id, editor.pubkey().as_ref()],
        &id(),
    );
    let grant = Instruction {
        program_id: id(),
        accounts: program_accounts::GrantEditor {
            asset,
            editor_grant,
            creator: creator.pubkey(),
            system_program: anchor_lang::system_program::ID,
        }
        .to_account_metas(None),
        data: program_instruction::GrantEditor {
            origin_id,
            editor: editor.pubkey(),
            permissions: 1,
            expires_at: 0,
        }
        .data(),
    };
    send(&mut svm, &creator, grant).unwrap();

    let child_id = [25; 32];
    let (child, _) = anchor_lang::prelude::Pubkey::find_program_address(&[b"version", &origin_id, &child_id], &id());
    let create_child = Instruction {
        program_id: id(),
        accounts: program_accounts::CreateVersion {
            registry,
            asset,
            parent_version: root_version,
            version: child,
            editor_grant: Some(editor_grant),
            actor: editor.pubkey(),
            system_program: anchor_lang::system_program::ID,
        }
        .to_account_metas(None),
        data: program_instruction::CreateVersion {
            origin_id,
            version_id: child_id,
            parent_version_id: root_id,
            content_hash: [26; 32],
            manifest_hash: [27; 32],
            manifest_uri_hash: [0; 32],
            action_type: ActionType::AiModify,
        }
        .data(),
    };
    send(&mut svm, &editor, create_child.clone()).unwrap();

    let revoke = Instruction {
        program_id: id(),
        accounts: program_accounts::RevokeEditor {
            asset,
            editor_grant,
            creator: creator.pubkey(),
        }
        .to_account_metas(None),
        data: program_instruction::RevokeEditor { origin_id, editor: editor.pubkey() }.data(),
    };
    send(&mut svm, &creator, revoke).unwrap();

    let revoked_child_id = [28; 32];
    let (revoked_child, _) = anchor_lang::prelude::Pubkey::find_program_address(
        &[b"version", &origin_id, &revoked_child_id], &id()
    );
    let mut revoked_instruction = create_child;
    revoked_instruction.accounts.iter_mut().find(|meta| meta.is_writable && meta.pubkey != asset).unwrap().pubkey = revoked_child;
    let mut data = revoked_instruction.data;
    data[8 + 32..8 + 64].copy_from_slice(&revoked_child_id);
    revoked_instruction.data = data;
    assert!(send(&mut svm, &editor, revoked_instruction).is_err());
}

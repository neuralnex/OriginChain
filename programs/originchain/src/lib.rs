use anchor_lang::prelude::*;

declare_id!("J6grB9Db5FjKYkGLWf4n81BZg75WEE9KVXbnq5XZBcg1");

pub const CREATE_VERSION_PERMISSION: u8 = 1;
pub const PROTOCOL_VERSION: u16 = 1;

#[program]
pub mod originchain_program {
    use super::*;

    pub fn initialize_registry(ctx: Context<InitializeRegistry>) -> Result<()> {
        let registry = &mut ctx.accounts.registry;
        registry.authority = ctx.accounts.authority.key();
        registry.protocol_version = PROTOCOL_VERSION;
        registry.paused = false;
        registry.bump = ctx.bumps.registry;
        Ok(())
    }

    pub fn set_paused(ctx: Context<SetPaused>, paused: bool) -> Result<()> {
        ctx.accounts.registry.paused = paused;
        emit!(RegistryPauseChanged { paused, authority: ctx.accounts.authority.key() });
        Ok(())
    }

    pub fn register_asset(
        ctx: Context<RegisterAsset>,
        origin_id: [u8; 32],
        root_version_id: [u8; 32],
        content_hash: [u8; 32],
        manifest_hash: [u8; 32],
        manifest_uri_hash: [u8; 32],
        identity_mode: IdentityMode,
    ) -> Result<()> {
        require!(is_nonzero(&origin_id), OriginChainError::InvalidOriginId);
        require!(is_nonzero(&root_version_id), OriginChainError::InvalidVersionId);
        require!(is_nonzero(&content_hash), OriginChainError::InvalidContentHash);
        require!(is_nonzero(&manifest_hash), OriginChainError::InvalidManifestHash);

        let now = Clock::get()?.unix_timestamp;
        let asset = &mut ctx.accounts.asset;
        asset.origin_id = origin_id;
        asset.creator = ctx.accounts.creator.key();
        asset.root_version_id = root_version_id;
        asset.version_count = 1;
        asset.identity_mode = identity_mode;
        asset.created_at = now;
        asset.bump = ctx.bumps.asset;

        let version = &mut ctx.accounts.root_version;
        version.origin_id = origin_id;
        version.version_id = root_version_id;
        version.parent_version_id = None;
        version.content_hash = content_hash;
        version.manifest_hash = manifest_hash;
        version.manifest_uri_hash = manifest_uri_hash;
        version.actor = ctx.accounts.creator.key();
        version.action_type = ActionType::Create;
        version.sequence = 0;
        version.created_at = now;
        version.bump = ctx.bumps.root_version;

        emit!(AssetRegistered {
            origin_id,
            root_version_id,
            creator: ctx.accounts.creator.key(),
            manifest_hash,
        });
        Ok(())
    }

    pub fn create_version(
        ctx: Context<CreateVersion>,
        origin_id: [u8; 32],
        version_id: [u8; 32],
        parent_version_id: [u8; 32],
        content_hash: [u8; 32],
        manifest_hash: [u8; 32],
        manifest_uri_hash: [u8; 32],
        action_type: ActionType,
    ) -> Result<()> {
        require!(is_nonzero(&version_id), OriginChainError::InvalidVersionId);
        require!(is_nonzero(&parent_version_id), OriginChainError::InvalidParentVersionId);
        require!(is_nonzero(&content_hash), OriginChainError::InvalidContentHash);
        require!(is_nonzero(&manifest_hash), OriginChainError::InvalidManifestHash);
        require!(
            content_hash != ctx.accounts.parent_version.content_hash,
            OriginChainError::UnchangedContent
        );
        require!(action_type != ActionType::Create, OriginChainError::InvalidChildAction);

        if ctx.accounts.actor.key() != ctx.accounts.asset.creator {
            let grant = ctx
                .accounts
                .editor_grant
                .as_ref()
                .ok_or(OriginChainError::UnauthorizedEditor)?;
            let actor_key = ctx.accounts.actor.key();
            let (expected_grant, _) = Pubkey::find_program_address(
                &[b"editor", origin_id.as_ref(), actor_key.as_ref()],
                ctx.program_id,
            );
            require_keys_eq!(grant.key(), expected_grant, OriginChainError::UnauthorizedEditor);
        }

        authorize_version_creation(
            &ctx.accounts.asset,
            ctx.accounts.actor.key(),
            ctx.accounts.editor_grant.as_ref().map(|grant| &**grant),
            origin_id,
            Clock::get()?.unix_timestamp,
        )?;

        let sequence = ctx.accounts.asset.version_count;
        ctx.accounts.asset.version_count = sequence
            .checked_add(1)
            .ok_or(OriginChainError::VersionCountOverflow)?;

        let now = Clock::get()?.unix_timestamp;
        let version = &mut ctx.accounts.version;
        version.origin_id = origin_id;
        version.version_id = version_id;
        version.parent_version_id = Some(parent_version_id);
        version.content_hash = content_hash;
        version.manifest_hash = manifest_hash;
        version.manifest_uri_hash = manifest_uri_hash;
        version.actor = ctx.accounts.actor.key();
        version.action_type = action_type;
        version.sequence = sequence;
        version.created_at = now;
        version.bump = ctx.bumps.version;

        emit!(VersionCreated {
            origin_id,
            version_id,
            parent_version_id,
            actor: ctx.accounts.actor.key(),
            manifest_hash,
            sequence,
            action_type,
        });
        Ok(())
    }

    pub fn grant_editor(
        ctx: Context<GrantEditor>,
        origin_id: [u8; 32],
        editor: Pubkey,
        permissions: u8,
        expires_at: i64,
    ) -> Result<()> {
        require!(permissions == CREATE_VERSION_PERMISSION, OriginChainError::InvalidEditorPermissions);
        let now = Clock::get()?.unix_timestamp;
        require!(expires_at == 0 || expires_at > now, OriginChainError::InvalidGrantExpiry);

        let grant = &mut ctx.accounts.editor_grant;
        grant.origin_id = origin_id;
        grant.editor = editor;
        grant.permissions = permissions;
        grant.expires_at = expires_at;
        grant.bump = ctx.bumps.editor_grant;
        emit!(EditorGranted { origin_id, editor, permissions, expires_at });
        Ok(())
    }

    pub fn revoke_editor(ctx: Context<RevokeEditor>, origin_id: [u8; 32], editor: Pubkey) -> Result<()> {
        emit!(EditorRevoked {
            origin_id,
            editor,
            revoked_by: ctx.accounts.creator.key(),
        });
        Ok(())
    }
}

fn is_nonzero(bytes: &[u8; 32]) -> bool {
    bytes.iter().any(|byte| *byte != 0)
}

fn authorize_version_creation(
    asset: &AssetAccount,
    actor: Pubkey,
    grant: Option<&EditorGrant>,
    origin_id: [u8; 32],
    now: i64,
) -> Result<()> {
    if actor == asset.creator {
        return Ok(());
    }
    let grant = grant.ok_or(OriginChainError::UnauthorizedEditor)?;
    require!(grant.origin_id == origin_id, OriginChainError::UnauthorizedEditor);
    require!(grant.editor == actor, OriginChainError::UnauthorizedEditor);
    require!(grant.permissions == CREATE_VERSION_PERMISSION, OriginChainError::UnauthorizedEditor);
    require!(grant.expires_at == 0 || grant.expires_at > now, OriginChainError::EditorGrantExpired);
    Ok(())
}

#[derive(Accounts)]
pub struct InitializeRegistry<'info> {
    #[account(init, payer = authority, space = 8 + RegistryConfig::INIT_SPACE, seeds = [b"registry"], bump)]
    pub registry: Account<'info, RegistryConfig>,
    #[account(mut)]
    pub authority: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct SetPaused<'info> {
    #[account(mut, seeds = [b"registry"], bump = registry.bump, has_one = authority)]
    pub registry: Account<'info, RegistryConfig>,
    pub authority: Signer<'info>,
}

#[derive(Accounts)]
#[instruction(origin_id: [u8; 32], root_version_id: [u8; 32])]
pub struct RegisterAsset<'info> {
    #[account(seeds = [b"registry"], bump = registry.bump, constraint = !registry.paused @ OriginChainError::RegistryPaused)]
    pub registry: Account<'info, RegistryConfig>,
    #[account(init, payer = creator, space = 8 + AssetAccount::INIT_SPACE, seeds = [b"asset", origin_id.as_ref()], bump)]
    pub asset: Account<'info, AssetAccount>,
    #[account(init, payer = creator, space = 8 + VersionAccount::INIT_SPACE, seeds = [b"version", origin_id.as_ref(), root_version_id.as_ref()], bump)]
    pub root_version: Account<'info, VersionAccount>,
    #[account(mut)]
    pub creator: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(origin_id: [u8; 32], version_id: [u8; 32], parent_version_id: [u8; 32])]
pub struct CreateVersion<'info> {
    #[account(seeds = [b"registry"], bump = registry.bump, constraint = !registry.paused @ OriginChainError::RegistryPaused)]
    pub registry: Account<'info, RegistryConfig>,
    #[account(mut, seeds = [b"asset", origin_id.as_ref()], bump = asset.bump, constraint = asset.origin_id == origin_id)]
    pub asset: Account<'info, AssetAccount>,
    #[account(seeds = [b"version", origin_id.as_ref(), parent_version_id.as_ref()], bump = parent_version.bump, constraint = parent_version.origin_id == origin_id && parent_version.version_id == parent_version_id)]
    pub parent_version: Account<'info, VersionAccount>,
    #[account(init, payer = actor, space = 8 + VersionAccount::INIT_SPACE, seeds = [b"version", origin_id.as_ref(), version_id.as_ref()], bump)]
    pub version: Account<'info, VersionAccount>,
    pub editor_grant: Option<Account<'info, EditorGrant>>,
    #[account(mut)]
    pub actor: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(origin_id: [u8; 32], editor: Pubkey)]
pub struct GrantEditor<'info> {
    #[account(mut, seeds = [b"asset", origin_id.as_ref()], bump = asset.bump, has_one = creator)]
    pub asset: Account<'info, AssetAccount>,
    #[account(init, payer = creator, space = 8 + EditorGrant::INIT_SPACE, seeds = [b"editor", origin_id.as_ref(), editor.as_ref()], bump)]
    pub editor_grant: Account<'info, EditorGrant>,
    #[account(mut)]
    pub creator: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(origin_id: [u8; 32], editor: Pubkey)]
pub struct RevokeEditor<'info> {
    #[account(seeds = [b"asset", origin_id.as_ref()], bump = asset.bump, has_one = creator)]
    pub asset: Account<'info, AssetAccount>,
    #[account(mut, close = creator, seeds = [b"editor", origin_id.as_ref(), editor.as_ref()], bump = editor_grant.bump, constraint = editor_grant.origin_id == origin_id && editor_grant.editor == editor)]
    pub editor_grant: Account<'info, EditorGrant>,
    #[account(mut)]
    pub creator: Signer<'info>,
}

#[account]
#[derive(InitSpace)]
pub struct RegistryConfig {
    pub authority: Pubkey,
    pub protocol_version: u16,
    pub paused: bool,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct AssetAccount {
    pub origin_id: [u8; 32],
    pub creator: Pubkey,
    pub root_version_id: [u8; 32],
    pub version_count: u64,
    pub identity_mode: IdentityMode,
    pub created_at: i64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct VersionAccount {
    pub origin_id: [u8; 32],
    pub version_id: [u8; 32],
    pub parent_version_id: Option<[u8; 32]>,
    pub content_hash: [u8; 32],
    pub manifest_hash: [u8; 32],
    pub manifest_uri_hash: [u8; 32],
    pub actor: Pubkey,
    pub action_type: ActionType,
    pub sequence: u64,
    pub created_at: i64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct EditorGrant {
    pub origin_id: [u8; 32],
    pub editor: Pubkey,
    pub permissions: u8,
    pub expires_at: i64,
    pub bump: u8,
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, Debug, InitSpace, PartialEq, Eq)]
pub enum IdentityMode {
    Anonymous,
    Pseudonymous,
    Credentialed,
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, Debug, InitSpace, PartialEq, Eq)]
pub enum ActionType {
    Create,
    Edit,
    AiModify,
    Transform,
    Compose,
}

#[event]
pub struct AssetRegistered {
    pub origin_id: [u8; 32],
    pub root_version_id: [u8; 32],
    pub creator: Pubkey,
    pub manifest_hash: [u8; 32],
}

#[event]
pub struct VersionCreated {
    pub origin_id: [u8; 32],
    pub version_id: [u8; 32],
    pub parent_version_id: [u8; 32],
    pub actor: Pubkey,
    pub manifest_hash: [u8; 32],
    pub sequence: u64,
    pub action_type: ActionType,
}

#[event]
pub struct EditorGranted {
    pub origin_id: [u8; 32],
    pub editor: Pubkey,
    pub permissions: u8,
    pub expires_at: i64,
}

#[event]
pub struct EditorRevoked {
    pub origin_id: [u8; 32],
    pub editor: Pubkey,
    pub revoked_by: Pubkey,
}

#[event]
pub struct RegistryPauseChanged {
    pub paused: bool,
    pub authority: Pubkey,
}

#[error_code]
pub enum OriginChainError {
    #[msg("Origin ID must not be all zeroes")]
    InvalidOriginId,
    #[msg("Version ID must not be all zeroes")]
    InvalidVersionId,
    #[msg("Parent version ID must not be all zeroes")]
    InvalidParentVersionId,
    #[msg("Content hash must not be all zeroes")]
    InvalidContentHash,
    #[msg("Manifest hash must not be all zeroes")]
    InvalidManifestHash,
    #[msg("The registry is paused")]
    RegistryPaused,
    #[msg("The resulting content hash is unchanged")]
    UnchangedContent,
    #[msg("A child version cannot use the create action")]
    InvalidChildAction,
    #[msg("Actor is not authorized to create a version")]
    UnauthorizedEditor,
    #[msg("Editor grant has expired")]
    EditorGrantExpired,
    #[msg("Editor grant must include version creation permission")]
    InvalidEditorPermissions,
    #[msg("Editor grant expiry must be zero or in the future")]
    InvalidGrantExpiry,
    #[msg("Version count overflow")]
    VersionCountOverflow,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn identifiers_reject_zero_values() {
        assert!(!is_nonzero(&[0; 32]));
        assert!(is_nonzero(&[1; 32]));
    }

    #[test]
    fn version_creator_and_valid_editor_are_authorized() {
        let asset = AssetAccount {
            origin_id: [1; 32],
            creator: Pubkey::new_unique(),
            root_version_id: [2; 32],
            version_count: 1,
            identity_mode: IdentityMode::Pseudonymous,
            created_at: 0,
            bump: 1,
        };
        let editor = Pubkey::new_unique();
        let grant = EditorGrant {
            origin_id: asset.origin_id,
            editor,
            permissions: CREATE_VERSION_PERMISSION,
            expires_at: 0,
            bump: 1,
        };
        assert!(authorize_version_creation(&asset, asset.creator, None, asset.origin_id, 10).is_ok());
        assert!(authorize_version_creation(&asset, editor, Some(&grant), asset.origin_id, 10).is_ok());
        assert!(authorize_version_creation(&asset, editor, None, asset.origin_id, 10).is_err());
        assert!(authorize_version_creation(&asset, editor, Some(&grant), asset.origin_id, 11).is_ok());

        let expired = EditorGrant { expires_at: 9, ..grant };
        assert!(authorize_version_creation(&asset, editor, Some(&expired), asset.origin_id, 10).is_err());
        let wrong_origin = EditorGrant { origin_id: [9; 32], ..grant };
        assert!(authorize_version_creation(&asset, editor, Some(&wrong_origin), asset.origin_id, 10).is_err());
        let unknown_permission = EditorGrant {
            permissions: CREATE_VERSION_PERMISSION | 2,
            ..grant
        };
        assert!(authorize_version_creation(&asset, editor, Some(&unknown_permission), asset.origin_id, 10).is_err());
    }
}

use chrono::{SecondsFormat, Utc};
use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use mime_guess::MimeGuess;
use notify::{Event, RecommendedWatcher, RecursiveMode, Watcher};
use rusqlite::{params, Connection, OptionalExtension};
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::env;
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::os::unix::fs::{OpenOptionsExt, PermissionsExt};
use std::path::{Path, PathBuf};
use std::sync::mpsc;
use std::thread;
use std::time::{Duration, UNIX_EPOCH};

const MANIFEST_DOMAIN: &[u8] = b"ORIGINCHAIN:MANIFEST:V1\0";
const SIGNATURE_DOMAIN: &[u8] = b"ORIGINCHAIN:MANIFEST-SIGNATURE:V1\0";
const EVENT_DOMAIN: &[u8] = b"ORIGINCHAIN:RUNTIME-EVENT:V1\0";
struct Runtime {
    db: Connection,
    signer: SigningKey,
    device_id: String,
}

fn main() {
    if let Err(error) = run() {
        eprintln!("originchain-runtime: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().skip(1).collect();
    match args.first().map(String::as_str) {
        Some("init") if args.len() == 2 => initialize(Path::new(&args[1])),
        Some("add-folder") if args.len() == 3 => add_folder(Path::new(&args[1]), Path::new(&args[2])),
        Some("exclude") if args.len() == 3 => set_exclusion(Path::new(&args[1]), Path::new(&args[2]), true),
        Some("include") if args.len() == 3 => set_exclusion(Path::new(&args[1]), Path::new(&args[2]), false),
        Some("pause") if args.len() == 2 => set_paused(Path::new(&args[1]), true),
        Some("resume") if args.len() == 2 => set_paused(Path::new(&args[1]), false),
        Some("list") if args.len() == 2 => list_records(Path::new(&args[1])),
        Some("status") if args.len() == 2 => show_status(Path::new(&args[1])),
        Some("watch") if args.len() == 2 => watch(Path::new(&args[1])),
        _ => {
            eprintln!("Usage:\n  originchain-runtime init <state-dir>\n  originchain-runtime add-folder <state-dir> <folder>\n  originchain-runtime exclude|include <state-dir> <folder>\n  originchain-runtime pause|resume|list|status|watch <state-dir>");
            Err("invalid command".into())
        }
    }
}

fn db_path(state_dir: &Path) -> PathBuf { state_dir.join("runtime.sqlite3") }

fn initialize(state_dir: &Path) -> Result<(), Box<dyn std::error::Error>> {
    fs::create_dir_all(state_dir)?;
    fs::set_permissions(state_dir, fs::Permissions::from_mode(0o700))?;
    let key_path = state_dir.join("device-ed25519.key");
    if !key_path.exists() {
        let mut seed = [0u8; 32];
        File::open("/dev/urandom")?.read_exact(&mut seed)?;
        let mut file = OpenOptions::new().write(true).create_new(true).mode(0o600).open(&key_path)?;
        file.write_all(&seed)?;
        file.sync_all()?;
    }
    fs::set_permissions(&key_path, fs::Permissions::from_mode(0o600))?;
    let _runtime = open_runtime(state_dir)?;
    println!("Initialized local OriginChain runtime at {}", state_dir.display());
    Ok(())
}

fn open_runtime(state_dir: &Path) -> Result<Runtime, Box<dyn std::error::Error>> {
    if !state_dir.is_dir() { return Err(format!("runtime state directory {} does not exist; run init first", state_dir.display()).into()); }
    let key_path = state_dir.join("device-ed25519.key");
    let mut seed = [0u8; 32];
    File::open(&key_path)?.read_exact(&mut seed)?;
    let signer = SigningKey::from_bytes(&seed);
    let device_id = bs58::encode(signer.verifying_key().as_bytes()).into_string();
    let db = Connection::open(db_path(state_dir))?;
    db.pragma_update(None, "journal_mode", "WAL")?;
    db.pragma_update(None, "foreign_keys", "ON")?;
    db.execute_batch(
        "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
         CREATE TABLE IF NOT EXISTS watched_roots (path TEXT PRIMARY KEY);
         CREATE TABLE IF NOT EXISTS exclusions (path TEXT PRIMARY KEY);
         CREATE TABLE IF NOT EXISTS assets (
           origin_id TEXT PRIMARY KEY, version_id TEXT NOT NULL, content_hash TEXT NOT NULL,
           media_type TEXT NOT NULL, size_bytes INTEGER NOT NULL, manifest_json TEXT NOT NULL,
           signature_json TEXT NOT NULL, evidence_state TEXT NOT NULL,
           first_observed_at TEXT NOT NULL, last_observed_at TEXT NOT NULL
         );
         CREATE TABLE IF NOT EXISTS file_mappings (
           path TEXT PRIMARY KEY, origin_id TEXT NOT NULL, version_id TEXT NOT NULL,
           content_hash TEXT NOT NULL, last_observed_at TEXT NOT NULL,
           FOREIGN KEY(origin_id) REFERENCES assets(origin_id)
         );
         CREATE TABLE IF NOT EXISTS events (
           event_id TEXT PRIMARY KEY, device_id TEXT NOT NULL, observed_at TEXT NOT NULL,
           event_type TEXT NOT NULL, evidence_level TEXT NOT NULL, origin_id TEXT,
           version_id TEXT, before_hash TEXT, after_hash TEXT, result_state TEXT NOT NULL,
           event_json TEXT NOT NULL, signature TEXT NOT NULL
         );
         INSERT OR IGNORE INTO settings(key, value) VALUES ('paused', 'false');"
    )?;
    Ok(Runtime { db, signer, device_id })
}

fn canonical_path(path: &Path) -> Result<PathBuf, Box<dyn std::error::Error>> {
    if !path.is_dir() { return Err(format!("{} is not an accessible directory", path.display()).into()); }
    Ok(path.canonicalize()?)
}

fn add_folder(state_dir: &Path, folder: &Path) -> Result<(), Box<dyn std::error::Error>> {
    let runtime = open_runtime(state_dir)?;
    let path = canonical_path(folder)?;
    runtime.db.execute("INSERT OR IGNORE INTO watched_roots(path) VALUES (?1)", [path.to_string_lossy().as_ref()])?;
    println!("Watching will be enabled for {} when the runtime starts", path.display());
    Ok(())
}

fn set_exclusion(state_dir: &Path, folder: &Path, exclude: bool) -> Result<(), Box<dyn std::error::Error>> {
    let runtime = open_runtime(state_dir)?;
    let path = canonical_path(folder)?;
    if exclude {
        runtime.db.execute("INSERT OR IGNORE INTO exclusions(path) VALUES (?1)", [path.to_string_lossy().as_ref()])?;
        println!("Excluded {}", path.display());
    } else {
        runtime.db.execute("DELETE FROM exclusions WHERE path = ?1", [path.to_string_lossy().as_ref()])?;
        println!("Included {}", path.display());
    }
    Ok(())
}

fn set_paused(state_dir: &Path, paused: bool) -> Result<(), Box<dyn std::error::Error>> {
    let runtime = open_runtime(state_dir)?;
    runtime.db.execute("INSERT INTO settings(key,value) VALUES('paused',?1) ON CONFLICT(key) DO UPDATE SET value=excluded.value", [paused.to_string()])?;
    println!("Local media observation {}", if paused { "paused" } else { "resumed; reconciliation runs in the active watcher" });
    Ok(())
}

fn show_status(state_dir: &Path) -> Result<(), Box<dyn std::error::Error>> {
    let runtime = open_runtime(state_dir)?;
    let paused = is_paused(&runtime.db)?;
    let roots: Vec<String> = runtime.db.prepare("SELECT path FROM watched_roots ORDER BY path")?
        .query_map([], |row| row.get(0))?.collect::<Result<_, _>>()?;
    let excluded: Vec<String> = runtime.db.prepare("SELECT path FROM exclusions ORDER BY path")?
        .query_map([], |row| row.get(0))?.collect::<Result<_, _>>()?;
    println!("Device ID: {}\nWatching: {}", runtime.device_id, if paused { "paused" } else { "active when watcher is running" });
    for root in roots { println!("  root: {root}"); }
    for path in excluded { println!("  excluded: {path}"); }
    Ok(())
}

fn list_records(state_dir: &Path) -> Result<(), Box<dyn std::error::Error>> {
    let runtime = open_runtime(state_dir)?;
    let mut stmt = runtime.db.prepare("SELECT origin_id, version_id, content_hash, media_type, size_bytes, evidence_state FROM assets ORDER BY first_observed_at")?;
    let rows = stmt.query_map([], |row| Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?, row.get::<_, String>(2)?, row.get::<_, String>(3)?, row.get::<_, i64>(4)?, row.get::<_, String>(5)?)))?;
    for row in rows {
        let (origin, version, hash, media, size, state) = row?;
        println!("{state}\t{media}\t{size} bytes\n  origin: {origin}\n  version: {version}\n  sha256: {hash}");
    }
    Ok(())
}

fn watch(state_dir: &Path) -> Result<(), Box<dyn std::error::Error>> {
    let runtime = open_runtime(state_dir)?;
    let roots: Vec<PathBuf> = runtime.db.prepare("SELECT path FROM watched_roots ORDER BY path")?
        .query_map([], |row| row.get::<_, String>(0))?.map(|row| row.map(PathBuf::from)).collect::<Result<_, _>>()?;
    if roots.is_empty() { return Err("add at least one folder before starting watch".into()); }
    let (tx, rx) = mpsc::channel();
    let mut watcher: RecommendedWatcher = notify::recommended_watcher(move |result| { let _ = tx.send(result); })?;
    for root in &roots { watcher.watch(root, RecursiveMode::Recursive)?; }
    let mut runtime = runtime;
    if !is_paused(&runtime.db)? {
        for root in &roots { reconcile(&mut runtime, root)?; }
    }
    println!("OriginChain Linux runtime is watching {} configured root(s). Ctrl-C stops observation.", roots.len());
    let mut was_paused = is_paused(&runtime.db)?;
    loop {
        match rx.recv_timeout(Duration::from_millis(500)) {
            Ok(Ok(event)) => {
                let paused = is_paused(&runtime.db)?;
                if was_paused && !paused { for root in &roots { reconcile(&mut runtime, root)?; } }
                was_paused = paused;
                if paused { continue; }
                handle_event(&mut runtime, event)?;
            }
            Ok(Err(error)) => eprintln!("watch event error (reconciliation is required): {error}"),
            Err(mpsc::RecvTimeoutError::Timeout) => {
                let paused = is_paused(&runtime.db)?;
                if was_paused && !paused { for root in &roots { reconcile(&mut runtime, root)?; } }
                was_paused = paused;
            }
            Err(mpsc::RecvTimeoutError::Disconnected) => return Err("filesystem watcher stopped unexpectedly".into()),
        }
    }
}

fn handle_event(runtime: &mut Runtime, event: Event) -> Result<(), Box<dyn std::error::Error>> {
    for path in event.paths {
        if path.is_file() { process_file(runtime, &path)?; }
    }
    Ok(())
}

fn reconcile(runtime: &mut Runtime, root: &Path) -> Result<(), Box<dyn std::error::Error>> {
    let mut pending = vec![root.to_path_buf()];
    while let Some(directory) = pending.pop() {
        if excluded(&runtime.db, &directory)? { continue; }
        let entries = match fs::read_dir(&directory) { Ok(entries) => entries, Err(error) => { eprintln!("cannot scan {}: {error}", directory.display()); continue; } };
        for entry in entries {
            let entry = match entry { Ok(entry) => entry, Err(error) => { eprintln!("directory entry error: {error}"); continue; } };
            let path = entry.path();
            let metadata = match fs::symlink_metadata(&path) { Ok(meta) => meta, Err(_) => continue };
            if metadata.file_type().is_symlink() { continue; }
            if metadata.is_dir() { pending.push(path); }
            else if metadata.is_file() { process_file(runtime, &path)?; }
        }
    }
    Ok(())
}

fn excluded(db: &Connection, path: &Path) -> Result<bool, Box<dyn std::error::Error>> {
    let exclusions: Vec<String> = db.prepare("SELECT path FROM exclusions")?
        .query_map([], |row| row.get(0))?.collect::<Result<_, _>>()?;
    Ok(exclusions.iter().any(|item| path.starts_with(item)))
}

fn process_file(runtime: &mut Runtime, path: &Path) -> Result<(), Box<dyn std::error::Error>> {
    if excluded(&runtime.db, path)? || is_sidecar(path) { return Ok(()); }
    let mime = media_type(path);
    if mime.is_none() { return Ok(()); }
    let (before_len, before_modified) = file_stamp(path)?;
    thread::sleep(Duration::from_millis(250));
    let (after_len, after_modified) = match file_stamp(path) { Ok(stamp) => stamp, Err(_) => return Ok(()) };
    if (before_len, before_modified) != (after_len, after_modified) { return Ok(()); }
    let content_hash = hash_file(path)?;
    if file_stamp(path).ok() != Some((after_len, after_modified)) { return Ok(()); }
    let observed_at = now();
    let path_text = path.to_string_lossy().into_owned();
    let sidecar = sidecar_path(path);

    // A tracked path's sidecar describes its previous bytes after an edit.
    // Resolve the mapping first, and keep reconciliation of unchanged files quiet.
    let prior: Option<(String, String, String)> = runtime.db.query_row(
        "SELECT origin_id,version_id,content_hash FROM file_mappings WHERE path=?1", [&path_text],
        |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
    ).optional()?;
    if let Some((origin, version, prior_hash)) = prior {
        if prior_hash == content_hash {
            runtime.db.execute("UPDATE file_mappings SET last_observed_at=?1 WHERE path=?2", params![observed_at, path_text])?;
            runtime.db.execute("UPDATE assets SET last_observed_at=?1 WHERE origin_id=?2", params![observed_at, origin])?;
        } else {
            runtime.db.execute("UPDATE assets SET evidence_state='pending_user_review',last_observed_at=?1 WHERE origin_id=?2", params![observed_at, origin])?;
            record_event(runtime, "observed_change", Some(&origin), Some(&version), Some(&prior_hash), Some(&content_hash), "pending_user_review", json!({"path": path_text}))?;
            eprintln!("changed tracked file requires review: {}", path.display());
        }
        return Ok(());
    }

    if sidecar.exists() {
        let package: Value = match serde_json::from_slice(&fs::read(&sidecar)?) {
            Ok(value) => value,
            Err(error) => { record_event(runtime, "manifest_imported", None, None, None, Some(&content_hash), "failed", json!({"error": format!("invalid sidecar JSON: {error}")}))?; return Ok(()); }
        };
        if verify_sidecar(&package, &content_hash, after_len as u64)? &&
           package.get("manifest").and_then(|m| m.get("media_type")).and_then(Value::as_str) == mime.as_deref() {
            let core = package.get("manifest").unwrap();
            let envelope = package.get("signature").unwrap();
            let origin = string_field(core, "origin_id")?;
            let version = string_field(core, "version_id")?;
            let manifest_json = canonical_json(core)?;
            let signature_json = serde_json::to_string(envelope)?;
            runtime.db.execute(
                "INSERT OR IGNORE INTO assets(origin_id,version_id,content_hash,media_type,size_bytes,manifest_json,signature_json,evidence_state,first_observed_at,last_observed_at) VALUES(?1,?2,?3,?4,?5,?6,?7,'local_only',?8,?8)",
                params![origin, version, content_hash, mime.unwrap(), after_len as i64, manifest_json, signature_json, observed_at],
            )?;
            runtime.db.execute("INSERT OR REPLACE INTO file_mappings(path,origin_id,version_id,content_hash,last_observed_at) VALUES(?1,?2,?3,?4,?5)", params![path_text, origin, version, content_hash, observed_at])?;
            record_event(runtime, "manifest_imported", Some(&origin), Some(&version), None, Some(&content_hash), "local_only", json!({"path": path_text}))?;
            println!("Imported signed OriginChain identity for {}", path.display());
        } else {
            record_event(runtime, "manifest_imported", None, None, None, Some(&content_hash), "failed", json!({"path": path_text, "reason": "sidecar signature, manifest, or file hash did not validate"}))?;
            eprintln!("identity sidecar did not verify for {}; left unchanged", path.display());
        }
        return Ok(());
    }

    let same_bytes: Option<(String, String)> = runtime.db.query_row(
        "SELECT origin_id,version_id FROM assets WHERE content_hash=?1 LIMIT 1", [&content_hash],
        |row| Ok((row.get(0)?, row.get(1)?)),
    ).optional()?;
    if let Some((origin, version)) = same_bytes {
        record_event(runtime, "observed_copy", Some(&origin), Some(&version), None, Some(&content_hash), "pending_user_review", json!({"path": path_text, "reason": "byte-identical local version found; identity is not merged without a valid sidecar or user confirmation"}))?;
        eprintln!("byte-identical local record found; review identity for {}", path.display());
        return Ok(());
    }

    let (core, envelope, digest) = create_root_manifest(runtime, &content_hash, mime.as_deref().unwrap(), after_len as u64)?;
    let origin = string_field(&core, "origin_id")?;
    let version = string_field(&core, "version_id")?;
    let manifest_json = canonical_json(&core)?;
    let signature_json = serde_json::to_string(&envelope)?;
    let package = json!({"manifest": core, "signature": envelope});
    write_sidecar(&sidecar, &package)?;
    runtime.db.execute(
        "INSERT INTO assets(origin_id,version_id,content_hash,media_type,size_bytes,manifest_json,signature_json,evidence_state,first_observed_at,last_observed_at) VALUES(?1,?2,?3,?4,?5,?6,?7,'local_only',?8,?8)",
        params![origin, version, content_hash, mime.unwrap(), after_len as i64, manifest_json, signature_json, observed_at],
    )?;
    runtime.db.execute("INSERT OR REPLACE INTO file_mappings(path,origin_id,version_id,content_hash,last_observed_at) VALUES(?1,?2,?3,?4,?5)", params![path_text.clone(), origin, version, content_hash, observed_at])?;
    record_event(runtime, "observed_import", Some(&origin), Some(&version), None, Some(&content_hash), "local_only", json!({"path": path_text, "manifest_hash": digest, "attribution": "unknown; runtime observed these bytes"}))?;
    println!("Assigned local Origin {origin} and Version {version} to {}", path.display());
    Ok(())
}

fn create_root_manifest(runtime: &Runtime, content_hash: &str, media_type: &str, size: u64) -> Result<(Value, Value, String), Box<dyn std::error::Error>> {
    let core = json!({
        "protocol": "originchain", "protocol_version": "1.0.0",
        "origin_id": new_id()?, "version_id": new_id()?, "manifest_id": new_id()?,
        "parent_version_id": null, "content_hash": content_hash, "hash_algorithm": "sha-256",
        "media_type": media_type, "size_bytes": size,
        "actor": {"actor_id": runtime.device_id, "actor_type": "device"},
        "identity_mode": "pseudonymous", "action_type": "create", "relationship": "root", "created_at": now()
    });
    let mut preimage = MANIFEST_DOMAIN.to_vec();
    preimage.extend_from_slice(canonical_json(&core)?.as_bytes());
    let digest = Sha256::digest(preimage);
    let digest_hex = hex(&digest);
    let mut signed = SIGNATURE_DOMAIN.to_vec();
    signed.extend_from_slice(&digest);
    let signature = runtime.signer.sign(&signed);
    let envelope = json!({
        "algorithm": "Ed25519", "public_key": runtime.device_id,
        "signature": bs58::encode(signature.to_bytes()).into_string()
    });
    Ok((core, envelope, digest_hex))
}

fn verify_sidecar(package: &Value, expected_hash: &str, expected_size: u64) -> Result<bool, Box<dyn std::error::Error>> {
    let Some(core) = package.get("manifest") else { return Ok(false) };
    let Some(envelope) = package.get("signature") else { return Ok(false) };
    if string_field(core, "protocol")? != "originchain" || string_field(core, "protocol_version")? != "1.0.0" ||
       string_field(core, "hash_algorithm")? != "sha-256" || string_field(core, "content_hash")? != expected_hash ||
       core.get("size_bytes").and_then(Value::as_u64) != Some(expected_size) { return Ok(false); }
    let origin = decode_id(string_field(core, "origin_id")?)?;
    let version = decode_id(string_field(core, "version_id")?)?;
    let manifest_id = decode_id(string_field(core, "manifest_id")?)?;
    if origin.len() != 32 || version.len() != 32 || manifest_id.len() != 32 { return Ok(false); }
    let mut preimage = MANIFEST_DOMAIN.to_vec();
    preimage.extend_from_slice(canonical_json(core)?.as_bytes());
    let digest = Sha256::digest(preimage);
    let mut signed = SIGNATURE_DOMAIN.to_vec();
    signed.extend_from_slice(&digest);
    let public = decode_id(string_field(envelope, "public_key")?)?;
    let signature = decode_id(string_field(envelope, "signature")?)?;
    if public.len() != 32 || signature.len() != 64 { return Ok(false); }
    let public: [u8; 32] = public.try_into().unwrap();
    let verifying_key = match VerifyingKey::from_bytes(&public) { Ok(key) => key, Err(_) => return Ok(false) };
    let signature = Signature::from_slice(&signature)?;
    Ok(verifying_key.verify(&signed, &signature).is_ok())
}

fn record_event(runtime: &Runtime, event_type: &str, origin: Option<&str>, version: Option<&str>, before: Option<&str>, after: Option<&str>, result_state: &str, details: Value) -> Result<(), Box<dyn std::error::Error>> {
    let event_id = new_id()?;
    let observed_at = now();
    let mut payload = Map::new();
    payload.insert("event_id".into(), json!(event_id));
    payload.insert("device_id".into(), json!(runtime.device_id));
    payload.insert("observed_at".into(), json!(observed_at));
    payload.insert("event_type".into(), json!(event_type));
    payload.insert("evidence_level".into(), json!("runtime_observed"));
    payload.insert("origin_id".into(), json!(origin));
    payload.insert("version_id".into(), json!(version));
    payload.insert("before_hash".into(), json!(before));
    payload.insert("after_hash".into(), json!(after));
    payload.insert("result_state".into(), json!(result_state));
    payload.insert("details".into(), details);
    let payload = Value::Object(payload);
    let encoded = canonical_json(&payload)?;
    let mut message = EVENT_DOMAIN.to_vec();
    message.extend_from_slice(encoded.as_bytes());
    let signature = bs58::encode(runtime.signer.sign(&message).to_bytes()).into_string();
    runtime.db.execute(
        "INSERT INTO events(event_id,device_id,observed_at,event_type,evidence_level,origin_id,version_id,before_hash,after_hash,result_state,event_json,signature) VALUES(?1,?2,?3,?4,'runtime_observed',?5,?6,?7,?8,?9,?10,?11)",
        params![event_id, runtime.device_id, observed_at, event_type, origin, version, before, after, result_state, encoded, signature],
    )?;
    Ok(())
}

fn write_sidecar(path: &Path, package: &Value) -> Result<(), Box<dyn std::error::Error>> {
    let temporary = path.with_extension("originchain.json.tmp");
    let bytes = serde_json::to_vec_pretty(package)?;
    let mut file = OpenOptions::new().write(true).create(true).truncate(true).mode(0o600).open(&temporary)?;
    file.write_all(&bytes)?;
    file.sync_all()?;
    fs::rename(temporary, path)?;
    Ok(())
}

fn sidecar_path(path: &Path) -> PathBuf {
    let mut name = path.file_name().unwrap_or_default().to_os_string();
    name.push(".originchain.json");
    path.with_file_name(name)
}
fn is_sidecar(path: &Path) -> bool { path.file_name().and_then(|s| s.to_str()).is_some_and(|s| s.ends_with(".originchain.json") || s.ends_with(".originchain.json.tmp")) }

fn media_type(path: &Path) -> Option<String> {
    let mime: MimeGuess = mime_guess::from_path(path);
    let value = mime.first()?.essence_str().to_ascii_lowercase();
    (value.starts_with("image/") || value.starts_with("video/")).then_some(value)
}

fn file_stamp(path: &Path) -> io::Result<(u64, Option<Duration>)> {
    let meta = fs::metadata(path)?;
    Ok((meta.len(), meta.modified().ok().and_then(|m| m.duration_since(UNIX_EPOCH).ok())))
}

fn hash_file(path: &Path) -> io::Result<String> {
    let mut file = File::open(path)?;
    let mut digest = Sha256::new();
    let mut buffer = [0u8; 1024 * 1024];
    loop { let count = file.read(&mut buffer)?; if count == 0 { break; } digest.update(&buffer[..count]); }
    Ok(hex(&digest.finalize()))
}

fn new_id() -> io::Result<String> {
    loop {
        let mut bytes = [0u8; 32];
        File::open("/dev/urandom")?.read_exact(&mut bytes)?;
        if bytes.iter().any(|byte| *byte != 0) { return Ok(bs58::encode(bytes).into_string()); }
    }
}

fn decode_id(value: &str) -> Result<Vec<u8>, Box<dyn std::error::Error>> { Ok(bs58::decode(value).into_vec()?) }
fn string_field<'a>(value: &'a Value, name: &str) -> Result<&'a str, Box<dyn std::error::Error>> { value.get(name).and_then(Value::as_str).ok_or_else(|| format!("missing string field {name}").into()) }
fn hex(bytes: &[u8]) -> String { bytes.iter().map(|byte| format!("{byte:02x}")).collect() }
fn now() -> String { Utc::now().to_rfc3339_opts(SecondsFormat::Millis, true) }

fn canonical_json(value: &Value) -> Result<String, Box<dyn std::error::Error>> {
    Ok(match value {
        Value::Null => "null".to_owned(),
        Value::Bool(value) => value.to_string(),
        Value::Number(value) => {
            if !value.is_u64() { return Err("manifest numbers must be non-negative integers".into()); }
            value.to_string()
        }
        Value::String(value) => serde_json::to_string(value)?,
        Value::Array(values) => format!("[{}]", values.iter().map(canonical_json).collect::<Result<Vec<_>, _>>()?.join(",")),
        Value::Object(values) => {
            let mut keys: Vec<&String> = values.keys().collect();
            keys.sort_by(|a, b| a.encode_utf16().cmp(b.encode_utf16()));
            let members = keys.into_iter().map(|key| Ok(format!("{}:{}", serde_json::to_string(key)?, canonical_json(&values[key])?))).collect::<Result<Vec<_>, Box<dyn std::error::Error>>>()?;
            format!("{{{}}}", members.join(","))
        }
    })
}

fn is_paused(db: &Connection) -> Result<bool, Box<dyn std::error::Error>> {
    let value: String = db.query_row("SELECT value FROM settings WHERE key='paused'", [], |row| row.get(0))?;
    Ok(value == "true")
}

use rusqlite::{params, backup::Backup, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use std::{fs, path::PathBuf, time::{Duration, SystemTime, UNIX_EPOCH}};
use tauri::{AppHandle, Manager};
use tauri_plugin_dialog::DialogExt;

const DB_NAME: &str = "conta-fp360.sqlite3";
const MAX_VALUE_BYTES: usize = 180_000_000;

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StorageRow {
    pub key: String,
    pub value: String,
}

fn checked_namespace(namespace: &str) -> Result<(), String> {
    if matches!(namespace, "local" | "objects") { Ok(()) }
    else { Err("Espacio de almacenamiento desconocido".into()) }
}

fn checked_key(key: &str) -> Result<(), String> {
    if key.is_empty() || key.len() > 512 || key.contains('\0') {
        Err("Clave de almacenamiento incorrecta".into())
    } else { Ok(()) }
}

fn db_path(app: &AppHandle) -> Result<PathBuf, String> {
    let dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    fs::create_dir_all(&dir).map_err(|e| format!("No se pudo crear el directorio de datos: {e}"))?;
    Ok(dir.join(DB_NAME))
}

fn open_db(app: &AppHandle) -> Result<Connection, String> {
    let conn = Connection::open(db_path(app)?).map_err(|e| e.to_string())?;
    conn.busy_timeout(Duration::from_secs(8)).map_err(|e| e.to_string())?;
    conn.execute_batch(
        "PRAGMA journal_mode=WAL;
         PRAGMA synchronous=FULL;
         CREATE TABLE IF NOT EXISTS app_meta(
            key TEXT PRIMARY KEY NOT NULL,
            value TEXT NOT NULL
         );
         CREATE TABLE IF NOT EXISTS stored_items(
            namespace TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            PRIMARY KEY(namespace, key)
         );
         PRAGMA user_version=1;"
    ).map_err(|e| format!("No se pudo inicializar SQLite: {e}"))?;
    let identifier = app.config().identifier.as_str();
    let recorded: Option<String> = conn.query_row(
        "SELECT value FROM app_meta WHERE key='application_id'", [], |r| r.get(0)
    ).optional().map_err(|e| e.to_string())?;
    if recorded.as_deref().is_some_and(|value| value != identifier) {
        return Err("Esta base de datos pertenece a otra edición de CONTA FP360".into());
    }
    conn.execute(
        "INSERT OR IGNORE INTO app_meta(key,value) VALUES('application_id',?1)",
        params![identifier]
    ).map_err(|e| e.to_string())?;
    Ok(conn)
}

async fn blocking<T: Send + 'static>(
    f: impl FnOnce() -> Result<T, String> + Send + 'static
) -> Result<T, String> {
    tauri::async_runtime::spawn_blocking(f)
        .await.map_err(|e| format!("Error de almacenamiento: {e}"))?
}

#[tauri::command]
pub async fn sqlite_list(app: AppHandle, namespace: String) -> Result<Vec<StorageRow>, String> {
    checked_namespace(&namespace)?;
    blocking(move || {
        let conn = open_db(&app)?;
        let mut stmt = conn.prepare(
            "SELECT key, value FROM stored_items WHERE namespace=?1 ORDER BY key"
        ).map_err(|e| e.to_string())?;
        let items = stmt.query_map(params![namespace], |r|
            Ok(StorageRow { key: r.get(0)?, value: r.get(1)? })
        ).map_err(|e| e.to_string())?;
        items.collect::<Result<Vec<_>, _>>().map_err(|e| e.to_string())
    }).await
}

#[tauri::command]
pub async fn sqlite_get(app: AppHandle, namespace: String, key: String) -> Result<Option<String>, String> {
    checked_namespace(&namespace)?;
    checked_key(&key)?;
    blocking(move || {
        let conn = open_db(&app)?;
        conn.query_row(
            "SELECT value FROM stored_items WHERE namespace=?1 AND key=?2",
            params![namespace, key], |r| r.get(0)
        ).optional().map_err(|e| e.to_string())
    }).await
}

#[tauri::command]
pub async fn sqlite_put(app: AppHandle, namespace: String, key: String, value: String) -> Result<(), String> {
    checked_namespace(&namespace)?;
    checked_key(&key)?;
    if value.len() > MAX_VALUE_BYTES { return Err("El dato supera el tamaño máximo permitido".into()); }
    blocking(move || {
        let conn = open_db(&app)?;
        conn.execute(
            "INSERT INTO stored_items(namespace,key,value) VALUES(?1,?2,?3)
             ON CONFLICT(namespace,key) DO UPDATE SET value=excluded.value,
                 updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')",
            params![namespace, key, value]
        ).map_err(|e| e.to_string())?;
        Ok(())
    }).await
}

#[tauri::command]
pub async fn sqlite_put_many(app: AppHandle, namespace: String, entries: Vec<StorageRow>) -> Result<(), String> {
    checked_namespace(&namespace)?;
    if entries.len() > 10_000 { return Err("Demasiados registros para importar".into()); }
    for e in &entries {
        checked_key(&e.key)?;
        if e.value.len() > MAX_VALUE_BYTES {
            return Err(format!("El registro {} es demasiado grande", e.key));
        }
    }
    blocking(move || {
        let mut conn = open_db(&app)?;
        let tx = conn.transaction().map_err(|e| e.to_string())?;
        {
            let mut stmt = tx.prepare(
                "INSERT INTO stored_items(namespace,key,value) VALUES(?1,?2,?3)
                 ON CONFLICT(namespace,key) DO UPDATE SET value=excluded.value,
                     updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')"
            ).map_err(|e| e.to_string())?;
            for e in entries {
                stmt.execute(params![namespace, e.key, e.value]).map_err(|e| e.to_string())?;
            }
        }
        tx.commit().map_err(|e| e.to_string())?;
        Ok(())
    }).await
}

#[tauri::command]
pub async fn sqlite_delete(app: AppHandle, namespace: String, key: String) -> Result<(), String> {
    checked_namespace(&namespace)?;
    checked_key(&key)?;
    blocking(move || {
        let conn = open_db(&app)?;
        conn.execute("DELETE FROM stored_items WHERE namespace=?1 AND key=?2",
                     params![namespace,key]).map_err(|e| e.to_string())?;
        Ok(())
    }).await
}

/// Copia consistente mediante la API de SQLite: incluye las transacciones WAL ya confirmadas.
#[tauri::command]
pub async fn sqlite_backup(app: AppHandle) -> Result<bool, String> {
    blocking(move || {
        let default_name = if app.config().identifier.ends_with(".studio") {
            "CONTA-FP360-Studio-copia.sqlite3"
        } else { "CONTA-FP360-Aula-copia.sqlite3" };
        let selected = app.dialog().file()
            .set_title("Exportar copia de seguridad SQLite")
            .set_file_name(default_name)
            .add_filter("SQLite", &["sqlite3"])
            .blocking_save_file();
        let Some(selected) = selected else { return Ok(false); };
        let path = selected.into_path().map_err(|e| e.to_string())?;
        if path.exists() { return Err("Por seguridad, elija un nombre nuevo: no se sobrescriben copias existentes".into()); }
        let src = open_db(&app)?;
        let mut dest = Connection::open(&path).map_err(|e| e.to_string())?;
        let result = (|| -> Result<(), String> {
            let b = Backup::new(&src, &mut dest).map_err(|e| e.to_string())?;
            b.run_to_completion(64, Duration::from_millis(25), None)
                .map_err(|e| e.to_string())
        })();
        drop(dest);
        if result.is_err() { let _ = fs::remove_file(path); }
        result?;
        Ok(true)
    }).await
}

/// La restauración comprueba integridad y edición, y conserva una copia previa automática.
/// El frontend debe vaciar la cola de escrituras y recargar tras completar la operación.
#[tauri::command]
pub async fn sqlite_restore(app: AppHandle) -> Result<bool, String> {
    blocking(move || {
        let selected = app.dialog().file()
            .set_title("Restaurar copia SQLite de esta edición")
            .add_filter("SQLite", &["sqlite3", "db"])
            .blocking_pick_file();
        let Some(selected) = selected else { return Ok(false); };
        let path = selected.into_path().map_err(|e| e.to_string())?;
        let src = Connection::open_with_flags(
            &path, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY
        ).map_err(|e| format!("La copia no se puede abrir: {e}"))?;
        let check: String = src.query_row("PRAGMA integrity_check", [], |r| r.get(0))
            .map_err(|e| format!("Copia dañada: {e}"))?;
        if check != "ok" { return Err(format!("La copia no supera la revisión de integridad: {check}")); }
        let role: String = src.query_row(
            "SELECT value FROM app_meta WHERE key='application_id'", [], |r| r.get(0)
        ).map_err(|_| "No es una copia SQLite válida de CONTA FP360".to_owned())?;
        if role != app.config().identifier {
            return Err("La copia corresponde a otra aplicación (Studio/Aula). Operación cancelada".into());
        }
        let mut dest = open_db(&app)?;
        let safety_name = format!("antes-restauracion-{}.sqlite3",
            SystemTime::now().duration_since(UNIX_EPOCH)
                .map_err(|e| e.to_string())?.as_secs());
        let safety_path = db_path(&app)?.with_file_name(safety_name);
        let mut safety = Connection::open(&safety_path).map_err(|e| e.to_string())?;
        {
            let backup = Backup::new(&dest, &mut safety).map_err(|e| e.to_string())?;
            backup.run_to_completion(64, Duration::from_millis(25), None)
                .map_err(|e| format!("No se pudo asegurar la base anterior: {e}"))?;
        }
        drop(safety);
        {
            let restore = Backup::new(&src, &mut dest).map_err(|e| e.to_string())?;
            restore.run_to_completion(64, Duration::from_millis(25), None)
                .map_err(|e| format!("No se pudo restaurar la copia: {e}"))?;
        }
        Ok(true)
    }).await
}

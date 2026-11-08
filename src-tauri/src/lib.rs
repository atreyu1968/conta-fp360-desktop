mod updater;
mod storage;

use base64::Engine as _;
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_opener::OpenerExt;

/// Guarda bytes generados en el navegador mediante un diálogo nativo.
#[tauri::command]
async fn save_export(
    app: tauri::AppHandle,
    filename: String,
    base64_data: String,
    open_after: bool,
) -> Result<bool, String> {
    if base64_data.len() > 280_000_000 {
        return Err("El archivo supera el límite de 200 MB de esta versión".into());
    }
    let bytes = base64::engine::general_purpose::STANDARD
        .decode(base64_data)
        .map_err(|e| format!("Contenido codificado incorrectamente: {e}"))?;
    if bytes.len() > 200_000_000 {
        return Err("El archivo supera el límite de 200 MB de esta versión".into());
    }
    let clean_name: String = filename
        .chars()
        .filter(|c| !matches!(c, '/' | '\\' | '<' | '>' | ':' | '"' | '|' | '?' | '*') && !c.is_control())
        .take(160)
        .collect();
    let clean_name = if clean_name.trim().is_empty() {
        "CONTA_FP360_exportacion.bin".to_owned()
    } else {
        clean_name
    };
    let extension = std::path::Path::new(&clean_name)
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("bin")
        .to_ascii_lowercase();
    let handle = app.clone();
    tauri::async_runtime::spawn_blocking(move || -> Result<bool, String> {
        let selected = handle
            .dialog()
            .file()
            .set_title("Guardar archivo de CONTA FP360")
            .set_file_name(&clean_name)
            .add_filter("Archivo exportado", &[extension.as_str()])
            .blocking_save_file();
        let Some(selected) = selected else { return Ok(false); };
        let path = selected.into_path().map_err(|e| e.to_string())?;
        std::fs::write(&path, &bytes)
            .map_err(|e| format!("No se pudo escribir el archivo: {e}"))?;
        if open_after {
            handle.opener().open_path(path.to_string_lossy().into_owned(), None::<&str>)
                .map_err(|e| format!("Se guardó el archivo, pero no se pudo abrir: {e}"))?;
        }
        Ok(true)
    })
    .await
    .map_err(|e| format!("Error en el diálogo de guardado: {e}"))?
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Windows GUI applications do not have a console in release mode.
    // Capture startup panics (including Tauri/plugin initialization) to a
    // diagnostic file so that installation failures can be investigated.
    std::panic::set_hook(Box::new(|info| {
        let diagnostic = std::env::temp_dir().join("CONTA-FP360-arranque-error.txt");
        let details = format!(
            "CONTA FP360 2.3.0 - panic de arranque\\n{}\\n\\n{}\\n",
            info,
            std::backtrace::Backtrace::force_capture()
        );
        let _ = std::fs::write(diagnostic, details);
    }));
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            save_export,
            updater::cfp_check_update,
            updater::cfp_install_update,
            storage::sqlite_get,
            storage::sqlite_list,
            storage::sqlite_put,
            storage::sqlite_put_many,
            storage::sqlite_delete,
            storage::sqlite_backup,
            storage::sqlite_restore
        ])
        .run(tauri::generate_context!())
        .expect("No se pudo iniciar CONTA FP360 Desktop");
}

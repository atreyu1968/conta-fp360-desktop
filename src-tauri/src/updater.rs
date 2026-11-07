//! Actualizaciones firmadas desde GitHub Releases. Clave pública embebida, privada jamás incluida.
use serde::Serialize;
use tauri::AppHandle;
use tauri_plugin_updater::UpdaterExt;

#[derive(Serialize)]
pub struct UpdateStatus {
    pub enabled: bool,
    pub available: bool,
    pub version: Option<String>,
    pub notes: Option<String>,
}
fn public_key() -> Option<&'static str> {
    option_env!("CONTA_FP360_UPDATER_PUBKEY").filter(|s| !s.trim().is_empty())
}
fn manifest_url(app: &AppHandle) -> &'static str {
    if app.config().identifier.ends_with(".studio") {
        "https://github.com/atreyu1968/conta-fp360-desktop/releases/latest/download/studio-latest.json"
    } else {
        "https://github.com/atreyu1968/conta-fp360-desktop/releases/latest/download/aula-latest.json"
    }
}
#[tauri::command]
pub async fn cfp_check_update(app: AppHandle) -> Result<UpdateStatus, String> {
    let Some(key) = public_key() else {
        return Ok(UpdateStatus { enabled: false, available: false, version: None, notes: None });
    };
    let url = manifest_url(&app).parse().map_err(|e| format!("URL incorrecta: {e}"))?;
    let updater = app.updater_builder().pubkey(key)
        .endpoints(vec![url]).map_err(|e| e.to_string())?
        .build().map_err(|e| e.to_string())?;
    let maybe = updater.check().await.map_err(|e| e.to_string())?;
    Ok(match maybe {
        Some(u) => UpdateStatus { enabled: true, available: true, version: Some(u.version), notes: u.body },
        None => UpdateStatus { enabled: true, available: false, version: None, notes: None },
    })
}
#[tauri::command]
pub async fn cfp_install_update(app: AppHandle) -> Result<bool, String> {
    let key = public_key().ok_or_else(|| "El actualizador firmado no está configurado".to_owned())?;
    let url = manifest_url(&app).parse().map_err(|e| format!("URL incorrecta: {e}"))?;
    let updater = app.updater_builder().pubkey(key)
        .endpoints(vec![url]).map_err(|e| e.to_string())?
        .build().map_err(|e| e.to_string())?;
    let Some(update) = updater.check().await.map_err(|e| e.to_string())? else { return Ok(false); };
    update.download_and_install(|_, _| {}, || {}).await.map_err(|e| e.to_string())?;
    app.restart();
    #[allow(unreachable_code)]
    Ok(true)
}
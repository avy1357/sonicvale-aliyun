// src-tauri/src/commands.rs
// 自定义 Tauri 命令:对应原 Electron 的 ipcMain.handle

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use tauri::AppHandle;

/// select-voice-folder 命令的返回项
/// 对应原 electron/main.js 的 select-voice-folder IPC
#[derive(Debug, Serialize, Deserialize)]
pub struct VoiceFolderItem {
    pub voice_name: String,
    pub emotion_name: String,
    pub strength_name: String,
    pub reference_path: String,
}

/// 校验路径是否在允许的 SonicVale 目录下,防止目录遍历与越权访问
fn validate_user_path(path: &PathBuf) -> Result<PathBuf, String> {
    let canonical = path
        .canonicalize()
        .map_err(|e| format!("路径不存在或无法访问: {e}"))?;
    // 允许的根目录:用户主目录下的 SonicVale 与 文档目录下的 SonicVale
    let home = dirs_next::home_dir()
        .ok_or_else(|| "无法获取用户主目录".to_string())?
        .canonicalize()
        .map_err(|e| format!("主目录规范化失败: {e}"))?;
    let mut allowed_roots: Vec<PathBuf> = vec![home.join("SonicVale")];
    // 文档目录下的 SonicVale(若存在,则纳入允许范围)
    if let Some(doc) = dirs_next::document_dir() {
        if let Ok(canon) = doc.join("SonicVale").canonicalize() {
            allowed_roots.push(canon);
        }
    }
    for root in &allowed_roots {
        if canonical.starts_with(root) {
            return Ok(canonical);
        }
    }
    Err("安全限制:仅允许访问 SonicVale 相关目录".to_string())
}

/// 选择音色文件夹并扫描子目录结构
/// 目录结构约定:rootPath/<emotion>/<strength>.<ext>
/// 返回每个文件的 { voice_name, emotion_name, strength_name, reference_path }
#[tauri::command]
pub fn select_voice_folder(
    _app_handle: AppHandle,
    root_path: String,
) -> Result<Vec<VoiceFolderItem>, String> {
    let root = validate_user_path(&PathBuf::from(&root_path))?;
    let voice_name = root
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("unknown")
        .to_string();

    let entries = fs::read_dir(&root).map_err(|e| format!("读取目录失败: {e}"))?;

    let mut result = Vec::new();
    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        let emotion_name = path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("")
            .to_string();

        // 单个子目录读取失败时跳过而非中断整个扫描
        let files = match fs::read_dir(&path) {
            Ok(f) => f,
            Err(e) => {
                log::warn!("读取子目录 {:?} 失败,跳过: {e}", path);
                continue;
            }
        };
        for file_entry in files.flatten() {
            let file_path = file_entry.path();
            if !file_path.is_file() {
                continue;
            }
            // 文件名(不含扩展名)作为 strength_name
            let strength_name = file_path
                .file_stem()
                .and_then(|n| n.to_str())
                .unwrap_or("")
                .to_string();

            result.push(VoiceFolderItem {
                voice_name: voice_name.clone(),
                emotion_name: emotion_name.clone(),
                strength_name,
                reference_path: file_path.to_string_lossy().to_string(),
            });
        }
    }

    Ok(result)
}

/// 主动杀掉后端进程(供前端调用)
#[tauri::command]
pub fn kill_backend(_app_handle: AppHandle) -> Result<(), String> {
    // 前端通常无需调用,后端在窗口关闭时自动清理
    // 保留此命令以备未来需要(如重启后端)
    Ok(())
}

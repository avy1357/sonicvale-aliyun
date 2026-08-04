// src-tauri/src/lib.rs
// 应用主入口:插件注册、命令注册、后端进程生命周期管理

mod commands;
mod sidecar;

use std::sync::Mutex;
use tauri::{Manager, WindowEvent};

/// 全局后端进程句柄,用于退出时清理
struct BackendState {
    child: Mutex<Option<std::process::Child>>,
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(
            tauri_plugin_log::Builder::new()
                .level(log::LevelFilter::Info)
                .build(),
        )
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_os::init())
        .manage(BackendState {
            child: Mutex::new(None),
        })
        .setup(|app| {
            let app_handle = app.handle().clone();
            // 用独立线程启动后端并轮询就绪,避免阻塞 Tauri 主线程
            std::thread::spawn(move || {
                match sidecar::start_backend(&app_handle) {
                    Ok(child) => {
                        {
                            let state: tauri::State<BackendState> = app_handle.state();
                            // 锁中毒时也取到数据,避免二次 panic
                            *state.child.lock().unwrap_or_else(|e| e.into_inner()) = Some(child);
                        }
                        // 健康轮询,就绪后显示主窗口
                        if sidecar::wait_for_ready(60, 500) {
                            log::info!("后端就绪");
                        } else {
                            log::error!("后端未就绪:健康检查超时");
                        }
                        if let Some(window) = app_handle.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    Err(e) => {
                        log::error!("后端启动失败: {e}");
                        // 通过 webview eval 调用 alert 向用户提示,避免静默失败让用户无所适从
                        if let Some(window) = app_handle.get_webview_window("main") {
                            // 使用 serde_json 生成安全的 JS 字符串字面量,避免 XSS/JS 注入
                            let safe_msg = serde_json::to_string(&format!("后端启动失败: {}", e))
                                .unwrap_or_else(|_| "\"后端启动失败\"".to_string());
                            let _ = window.eval(&format!("alert({})", safe_msg));
                            let _ = window.show();
                        }
                    }
                }
            });
            Ok(())
        })
        .on_window_event(|window, event| {
            // 窗口关闭时触发后端清理
            if let WindowEvent::CloseRequested { .. } = event {
                let app_handle = window.app_handle();
                let state: tauri::State<BackendState> = app_handle.state();
                if let Some(child) = state.child.lock().unwrap_or_else(|e| e.into_inner()).take() {
                    sidecar::kill_backend_tree(child);
                };
            }
        })
        .invoke_handler(tauri::generate_handler![
            commands::select_voice_folder,
            commands::kill_backend,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

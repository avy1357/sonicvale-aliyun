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
                            *state.child.lock().unwrap() = Some(child);
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
                        if let Some(window) = app_handle.get_webview_window("main") {
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
                if let Some(child) = state.child.lock().unwrap().take() {
                    sidecar::kill_backend_tree(child);
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            commands::select_voice_folder,
            commands::kill_backend,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

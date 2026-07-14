// src-tauri/src/main.rs
// 防止 Windows 发布构建出现控制台窗口
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    sonicvale_lib::run()
}

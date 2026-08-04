// src-tauri/src/sidecar.rs
// 后端进程管理:启动、健康轮询、进程树清理

use std::io::{BufRead, BufReader, Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::time::Duration;
use tauri::{AppHandle, Manager};

const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: u16 = 8200;
const BACKEND_HEALTH_PATH: &str = "/docs";

// 后端可执行文件名按平台区分,避免硬编码 .exe 导致跨平台失效
#[cfg(target_os = "windows")]
const BACKEND_EXE: &str = "main.exe";
#[cfg(not(target_os = "windows"))]
const BACKEND_EXE: &str = "main";

/// 获取后端可执行文件路径
/// 优先使用 resource_dir(生产环境),回退到 CARGO_MANIFEST_DIR(开发环境)
fn get_backend_path(app_handle: &AppHandle) -> PathBuf {
    if let Ok(rd) = app_handle.path().resource_dir() {
        let p = rd.join(BACKEND_EXE);
        if p.exists() {
            return p;
        }
    }
    // dev 回退:src-tauri/resources/<backend_exe>
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("resources")
        .join(BACKEND_EXE)
}

/// 启动后端进程,返回子进程句柄
pub fn start_backend(app_handle: &AppHandle) -> std::io::Result<Child> {
    let exe_path = get_backend_path(app_handle);
    if !exe_path.exists() {
        return Err(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            format!("后端可执行文件不存在: {}", exe_path.display()),
        ));
    }

    log::info!("启动后端: {}", exe_path.display());

    let cwd = exe_path
        .parent()
        .map(|p| p.to_path_buf())
        .unwrap_or_else(|| PathBuf::from("."));

    let mut child = Command::new(&exe_path)
        .current_dir(&cwd)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;

    // 转发 stdout
    // 注:此转发线程目前没有显式退出机制,依赖子进程 stdout 关闭后 reader.lines() 自然结束
    // 若未来需要主动停止,可在 BackendState 中保存停止标志并在此处轮询
    if let Some(stdout) = child.stdout.take() {
        std::thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines().flatten() {
                log::info!("[后端] {}", decode_maybe_gbk(line.as_bytes()));
            }
        });
    }
    // 转发 stderr
    // 注:同上,依赖子进程 stderr 关闭后自然退出
    if let Some(stderr) = child.stderr.take() {
        std::thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line in reader.lines().flatten() {
                log::error!("[后端错误] {}", decode_maybe_gbk(line.as_bytes()));
            }
        });
    }

    Ok(child)
}

/// 解码可能为 GBK 的字节串:先尝试 UTF-8,失败则回退 GBK
fn decode_maybe_gbk(bytes: &[u8]) -> String {
    // UTF-8 解码器,遇非法字节返回 None
    match std::str::from_utf8(bytes) {
        Ok(s) => s.to_string(),
        Err(_) => {
            // 回退到 GBK 解码
            let (decoded, _, _) = encoding_rs::GBK.decode(bytes);
            decoded.to_string()
        }
    }
}

/// 健康检查:尝试 HTTP GET /docs,返回是否就绪
fn check_backend_ready() -> bool {
    let addr: SocketAddr = format!("{}:{}", BACKEND_HOST, BACKEND_PORT)
        .parse()
        .unwrap_or_else(|_| SocketAddr::from(([127, 0, 0, 1], BACKEND_PORT)));

    let mut stream = match TcpStream::connect_timeout(&addr, Duration::from_millis(800)) {
        Ok(s) => s,
        Err(_) => return false,
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(800)));

    let request = format!(
        "GET {} HTTP/1.0\r\nHost: {}\r\n\r\n",
        BACKEND_HEALTH_PATH, BACKEND_HOST
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }

    let mut buf = [0u8; 64];
    match stream.read(&mut buf) {
        Ok(n) if n > 0 => {
            let resp = String::from_utf8_lossy(&buf[..n]);
            // 校验响应行包含 200 状态码,避免后端端口被其他服务占用造成误判
            resp.starts_with("HTTP/1.0 200") || resp.starts_with("HTTP/1.1 200")
        }
        _ => false,
    }
}

/// 轮询等待后端就绪
/// retries: 最大重试次数;delay_ms: 每次重试间隔
pub fn wait_for_ready(retries: u32, delay_ms: u64) -> bool {
    for attempt in 0..retries {
        if check_backend_ready() {
            // 端口已通且 HTTP 有响应,再给 FastAPI 一点缓冲时间确保路由完全注册
            std::thread::sleep(Duration::from_millis(300));
            log::info!("后端健康检查通过(第 {} 次尝试)", attempt + 1);
            return true;
        }
        std::thread::sleep(Duration::from_millis(delay_ms));
    }
    false
}

/// 杀掉整个后端进程树
/// Windows: taskkill /PID {pid} /T /F(杀整个进程树)
/// Unix: child.kill()(SIGKILL,简化实现)
pub fn kill_backend_tree(mut child: Child) {
    let pid = child.id();
    log::info!("清理后端进程 pid={}", pid);

    #[cfg(target_os = "windows")]
    {
        match Command::new("taskkill")
            .args(["/PID", &pid.to_string(), "/T", "/F"])
            .output()
        {
            Ok(out) => {
                if !out.status.success() {
                    // taskkill 失败,尝试直接 kill
                    let _ = child.kill();
                }
            }
            Err(e) => {
                log::warn!("taskkill 执行失败: {e},回退到 child.kill()");
                let _ = child.kill();
            }
        }
    }

    #[cfg(not(target_os = "windows"))]
    {
        // Unix 简化处理:直接 SIGKILL
        let _ = child.kill();
    }

    let _ = child.wait();
}

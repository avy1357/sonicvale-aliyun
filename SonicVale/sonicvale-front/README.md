# 轻语云配前端 (sonicvale-front)

基于 Vue 3 + Vite + Tauri 的桌面应用前端，与 FastAPI 后端配合使用。

## 环境要求

- Node.js >= 18
- [Rust 工具链](https://rustup.rs)（Tauri 编译必需）
- WebView2 Runtime（Windows，Win11 自带）

## 开发

```bash
npm install
npm run start       # tauri dev，启动开发环境
```

开发模式下 Tauri 会自动拉起 Vite Dev Server（默认端口 5173）并加载。

## 构建

```bash
npm run electron-build    # tauri build，输出 NSIS 安装包
```

产物位于 `src-tauri/target/release/bundle/`。

## 后端 sidecar

打包前需将 PyInstaller 打包的后端可执行文件放入：

```
src-tauri/resources/main.exe
```

开发模式下可直接单独启动后端：

```bash
cd ../SonicVale
uvicorn app.main:app --reload --port 8200
```

## 目录结构

```
sonicvale-front/
├── src/                # Vue 前端源码
│   ├── api/            # 后端 API 封装
│   ├── pages/          # 页面组件
│   ├── components/     # 通用组件
│   ├── router/         # 路由
│   ├── utils/          # 工具函数（含 nativeBridge.js）
│   └── main.js
├── src-tauri/          # Tauri 主进程（Rust）
│   ├── src/            # Rust 源码
│   ├── resources/      # 后端可执行文件
│   ├── icons/          # 应用图标
│   └── tauri.conf.json # Tauri 配置
├── vite.config.js
└── package.json
```

## 原生能力桥接

前端通过 `src/utils/nativeBridge.js` 暴露的 `window.native` 对象调用系统能力（文件对话框、文件读写、打开目录等），该桥接层在 Tauri 之上实现，保持与原 Electron preload 一致的方法签名，业务代码无需感知底层框架。

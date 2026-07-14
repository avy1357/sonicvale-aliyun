// src/utils/nativeBridge.js
// Electron → Tauri 迁移兼容层
// 保持 window.native.* 调用签名与原 electron/preload.js 完全一致
// 前端业务代码无需修改,仅 getUserHome 由同步改为异步

import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { open as openDialog, save as saveDialog } from '@tauri-apps/plugin-dialog'
import { writeFile as fsWriteFile, copyFile as fsCopyFile } from '@tauri-apps/plugin-fs'
import { open as shellOpen } from '@tauri-apps/plugin-shell'
import { homeDir } from '@tauri-apps/api/path'

// 是否运行在 Tauri 环境(非 Tauri 环境降级为浏览器模式)
const isTauri =
  typeof window !== 'undefined' &&
  ('__TAURI_INTERNALS__' in window || '__TAURI__' in window)

/**
 * 选择参考音频文件
 * @returns {Promise<string|null>} 绝对路径,取消时为 null
 */
async function pickAudio() {
  if (!isTauri) return null
  try {
    const selected = await openDialog({
      title: '选择参考音频',
      multiple: false,
      filters: [{ name: 'Audio', extensions: ['mp3', 'wav', 'm4a', 'ogg', 'flac'] }]
    })
    return selected || null
  } catch (e) {
    console.error('[nativeBridge] pickAudio:', e)
    return null
  }
}

/**
 * 选择文件对话框
 * @param {Object} options - { title, filters }
 * @returns {Promise<string|null>}
 */
async function pickFile(options) {
  if (!isTauri) return null
  try {
    const selected = await openDialog({
      title: options?.title || '选择文件',
      multiple: false,
      filters: options?.filters || [{ name: '所有文件', extensions: ['*'] }]
    })
    return selected || null
  } catch (e) {
    console.error('[nativeBridge] pickFile:', e)
    return null
  }
}

/**
 * 选择目录对话框
 * @param {Object} options - { title }
 * @returns {Promise<string|null>}
 */
async function pickDirectory(options) {
  if (!isTauri) return null
  try {
    const selected = await openDialog({
      title: options?.title || '选择目录',
      directory: true,
      multiple: false
    })
    return selected || null
  } catch (e) {
    console.error('[nativeBridge] pickDirectory:', e)
    return null
  }
}

/**
 * 选择项目根路径文件夹(与 pickDirectory 语义相同,保留原名)
 * @returns {Promise<string|null>}
 */
async function selectDir() {
  if (!isTauri) return null
  try {
    const selected = await openDialog({
      title: '选择项目根路径',
      directory: true,
      multiple: false
    })
    return selected || null
  } catch (e) {
    console.error('[nativeBridge] selectDir:', e)
    return null
  }
}

/**
 * 保存文件对话框
 * @param {Object} options - { title, defaultPath, filters }
 * @returns {Promise<string|null>}
 */
async function saveFile(options) {
  if (!isTauri) return null
  try {
    const path = await saveDialog({
      title: options?.title || '保存文件',
      defaultPath: options?.defaultPath || '',
      filters: options?.filters || [{ name: '所有文件', extensions: ['*'] }]
    })
    return path || null
  } catch (e) {
    console.error('[nativeBridge] saveFile:', e)
    return null
  }
}

/**
 * 写入文件(用于音频下载等)
 * @param {string} filePath - 目标文件路径
 * @param {Uint8Array} data - 文件数据
 * @returns {Promise<{success: boolean, error?: string}>}
 */
async function writeFile(filePath, data) {
  if (!isTauri) return { success: false, error: 'not in tauri environment' }
  try {
    const bytes = data instanceof Uint8Array ? data : new Uint8Array(data)
    await fsWriteFile(filePath, bytes)
    return { success: true }
  } catch (e) {
    console.error('[nativeBridge] writeFile:', e)
    return { success: false, error: e?.message || String(e) }
  }
}

/**
 * 复制文件
 * @param {string} sourcePath
 * @param {string} destPath
 * @returns {Promise<{success: boolean, error?: string}>}
 */
async function copyFile(sourcePath, destPath) {
  if (!isTauri) return { success: false, error: 'not in tauri environment' }
  try {
    await fsCopyFile(sourcePath, destPath)
    return { success: true }
  } catch (e) {
    console.error('[nativeBridge] copyFile:', e)
    return { success: false, error: e?.message || String(e) }
  }
}

/**
 * 用系统资源管理器打开文件夹
 * @param {string} folderPath
 * @returns {Promise<boolean>}
 */
async function openFolder(folderPath) {
  if (!isTauri) return false
  if (!folderPath) return false
  try {
    await shellOpen(folderPath)
    return true
  } catch (e) {
    console.error('[nativeBridge] openFolder:', e)
    return false
  }
}

/**
 * 把绝对路径转换为可被 <audio>/wavesurfer 加载的 URL
 * Tauri 使用 asset:// 协议(需在 tauri.conf.json 启用 assetProtocol)
 * @param {string} p
 * @returns {string}
 */
function pathToFileUrl(p) {
  if (!p) return ''
  if (!isTauri) return p
  try {
    return convertFileSrc(p)
  } catch (e) {
    console.error('[nativeBridge] pathToFileUrl:', e)
    return p
  }
}

/**
 * 获取用户主目录
 * 注意:Tauri 的 homeDir 是异步的,与原 Electron 同步实现不同
 * 调用方需用 await
 * @returns {Promise<string>}
 */
async function getUserHome() {
  if (!isTauri) return ''
  try {
    return await homeDir()
  } catch (e) {
    console.error('[nativeBridge] getUserHome:', e)
    return ''
  }
}

/**
 * 选择音色文件夹并扫描子目录结构
 * 组合 dialog.open(选目录) + invoke('select_voice_folder')(扫描)
 * @returns {Promise<Array|null>}
 */
async function selectVoiceFolder() {
  if (!isTauri) return null
  try {
    const rootPath = await openDialog({
      title: '选择音色文件夹',
      directory: true,
      multiple: false
    })
    if (!rootPath) return null
    return await invoke('select_voice_folder', { rootPath })
  } catch (e) {
    console.error('[nativeBridge] selectVoiceFolder:', e)
    return null
  }
}

// 挂载到 window,保持与原 preload.js 的 window.native 一致
window.native = {
  pickAudio,
  pickFile,
  pickDirectory,
  selectDir,
  saveFile,
  writeFile,
  copyFile,
  openFolder,
  pathToFileUrl,
  getUserHome,
  selectVoiceFolder
}

export {
  pickAudio,
  pickFile,
  pickDirectory,
  selectDir,
  saveFile,
  writeFile,
  copyFile,
  openFolder,
  pathToFileUrl,
  getUserHome,
  selectVoiceFolder
}

import os
import sys
# 得到默认配置文件
def getConfigPath():
    # 用户 目录下SonicVale目录
    user_dir = os.path.join(os.path.expanduser("~"), "SonicVale")

    # 如果目录不存在，创建它
    if not os.path.exists(user_dir):
        # mode=0o700 限制属主权限(Unix 下生效; Windows 下无效但保留设置)
        os.makedirs(user_dir, exist_ok=True, mode=0o700)
        # Windows 下 makedirs 的 mode 参数无效,使用 icacls 设置目录权限(仅当前用户可访问)
        if sys.platform == "win32":
            try:
                import subprocess
                username = os.environ.get("USERNAME", "")
                if username:
                    subprocess.run(
                        ["icacls", user_dir, "/inheritance:r", "/grant:r", f"{username}:(OI)(CI)F"],
                        capture_output=True, check=False
                    )
            except Exception:
                pass  # 权限设置失败不阻塞程序启动

    # 返回 config.json 路径（目录已保证存在）
    return user_dir

def getFfmpegPath():
    BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # 根据平台选择可执行文件名:Windows 用 ffmpeg.exe,其他平台用 ffmpeg
    ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    FFMPEG_PATH = os.path.join(BASE_DIR, "core", "ffmpeg", ffmpeg_name)
    return FFMPEG_PATH
import os
import contextlib
import subprocess
import tempfile
import shutil
import logging
import soundfile as sf
import numpy as np

from app.core.config import getFfmpegPath
from app.core import path_security


class AudioProcessor:
    def __init__(self, audio_path: str, keep_format=True, default_sr=44100, default_ch=2):
        # 校验音频路径不指向系统关键目录
        path_security.assert_path_not_system_critical(audio_path)
        self.audio_path = audio_path
        self.keep_format = keep_format
        self.default_sr = default_sr
        self.default_ch = default_ch

        info = sf.info(audio_path)
        self.sr = info.samplerate if keep_format else default_sr
        self.ch = info.channels if keep_format else default_ch
        self.duration = info.duration

        self.ffmpeg_path = getFfmpegPath()
        self.temp_path = self._create_tmp_file()

    def _create_tmp_file(self):
        os.makedirs(os.path.dirname(self.audio_path) or ".", exist_ok=True)
        # 创建临时文件(mkstemp 会创建空文件,后续由 ffmpeg 覆盖写入),减少无用文件残留
        fd, path = tempfile.mkstemp(suffix=".wav",
                                     dir=os.path.dirname(self.audio_path) or ".")
        os.close(fd)  # 立即关闭 fd,仅保留路径
        return path

    def _run_ffmpeg(self, cmd):
        # 捕获 ffmpeg 输出,失败时记录 stderr 便于排查
        try:
            subprocess.run(
                cmd, check=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
        except subprocess.CalledProcessError as e:
            stderr_text = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            logging.error("ffmpeg 执行失败(返回码 %s): %s", e.returncode, stderr_text)
            raise

    def _process_and_replace(self, cmd):
        """执行 ffmpeg 命令并将结果替换到 audio_path,失败时清理临时文件"""
        try:
            self._run_ffmpeg(cmd)
            os.replace(self.temp_path, self.audio_path)
        except Exception:
            self.cleanup()
            raise

    def cleanup(self):
        """清理临时文件(如果存在)"""
        with contextlib.suppress(FileNotFoundError, OSError):
            os.remove(self.temp_path)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def _normalize(self, path):
        """防止音量削波"""
        data, sr = sf.read(path, dtype="float32", always_2d=True)
        peak = float(np.max(np.abs(data)))
        if peak > 1.0:
            data = data / peak
            sf.write(path, data, sr, format="WAV", subtype="PCM_16")

    # ---------------------- 模块功能 ---------------------- #

    def cut(self, start_ms: int, end_ms: int):
        """删除音频区间 [start_ms, end_ms]"""
        start_ms = float(start_ms)
        end_ms = float(end_ms)
        if start_ms < 0 or end_ms < 0:
            raise ValueError("start_ms 和 end_ms 必须非负")
        start_sec = float(start_ms / 1000)
        end_sec = float(end_ms / 1000)
        if start_sec < 0 or end_sec < 0:
            raise ValueError("start_sec 和 end_sec 必须非负")

        cmd = [
            self.ffmpeg_path, "-y", "-i", self.audio_path,
            "-filter_complex",
            f"[0:a]atrim=0:{start_sec},asetpts=PTS-STARTPTS[first];"
            f"[0:a]atrim={end_sec},asetpts=PTS-STARTPTS[second];"
            f"[first][second]concat=n=2:v=0:a=1[out]",
            "-map", "[out]",
            "-ar", str(self.sr),
            "-ac", str(self.ch),
            "-c:a", "pcm_s16le",
            self.temp_path
        ]
        self._process_and_replace(cmd)

    def insert_silence(self, insert_ms: int, duration_sec: float):
        """在指定时间点插入静音"""
        insert_ms = float(insert_ms)
        duration_sec = float(duration_sec)
        if insert_ms < 0 or duration_sec < 0:
            raise ValueError("insert_ms 和 duration_sec 必须非负")
        insert_sec = float(insert_ms / 1000)
        if insert_sec < 0:
            raise ValueError("insert_sec 必须非负")
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", self.audio_path,
            "-f", "lavfi", "-t", str(duration_sec),
            "-i", f"anullsrc=channel_layout={'stereo' if self.ch == 2 else 'mono'}:sample_rate={self.sr}",
            "-filter_complex",
            f"[0:a]atrim=0:{insert_sec},asetpts=PTS-STARTPTS[first];"
            f"[0:a]atrim={insert_sec},asetpts=PTS-STARTPTS[second];"
            f"[first][1:a][second]concat=n=3:v=0:a=1[out]",
            "-map", "[out]",
            "-ar", str(self.sr),
            "-ac", str(self.ch),
            "-c:a", "pcm_s16le",
            self.temp_path
        ]
        self._process_and_replace(cmd)

    def append_silence(self, duration_sec: float):
        """
        在音频末尾添加或裁剪静音段：
        - duration_sec > 0: 在末尾添加指定秒数静音
        - duration_sec < 0: 从末尾裁剪指定秒数的内容
        """
        duration_sec = float(duration_sec)
        if duration_sec == 0:
            return  # 无需处理

        # ---------- 情况1：添加静音 ----------
        if duration_sec > 0:
            cmd = [
                self.ffmpeg_path, "-y",
                "-i", self.audio_path,
                "-f", "lavfi", "-t", str(duration_sec),
                "-i", f"anullsrc=channel_layout={'stereo' if self.ch == 2 else 'mono'}:sample_rate={self.sr}",
                "-filter_complex",
                "[0:a][1:a]concat=n=2:v=0:a=1[out]",
                "-map", "[out]",
                "-ar", str(self.sr),
                "-ac", str(self.ch),
                "-c:a", "pcm_s16le",
                self.temp_path
            ]

        # ---------- 情况2：裁剪末尾 ----------
        else:
            cut_dur = float(self.duration + duration_sec)  # 因为 duration_sec 为负
            if cut_dur < 0:
                cut_dur = 0.0  # 防止全裁掉出错
            cmd = [
                self.ffmpeg_path, "-y",
                "-i", self.audio_path,
                "-filter_complex",
                f"[0:a]atrim=0:{cut_dur},asetpts=PTS-STARTPTS[out]",
                "-map", "[out]",
                "-ar", str(self.sr),
                "-ac", str(self.ch),
                "-c:a", "pcm_s16le",
                self.temp_path
            ]

        # 执行 ffmpeg 命令
        self._process_and_replace(cmd)
        # 更新音频时长（防止后续操作出错）
        info = sf.info(self.audio_path)
        self.duration = info.duration

    def change_speed(self, speed: float):
        """变速处理 (0.5~2.0倍)"""
        speed = float(speed)
        if speed < 0:
            raise ValueError("speed 必须非负")
        speed = float(np.clip(speed, 0.5, 2.0))
        cmd = [
            self.ffmpeg_path, "-y", "-i", self.audio_path,
            "-af", f"atempo={speed}",
            "-ar", str(self.sr),
            "-ac", str(self.ch),
            "-c:a", "pcm_s16le",
            self.temp_path
        ]
        self._process_and_replace(cmd)

    def change_volume(self, volume: float):
        """音量调整"""
        volume = float(volume)
        if volume < 0:
            raise ValueError("volume 必须非负")
        volume = max(0.0, volume)
        cmd = [
            self.ffmpeg_path, "-y", "-i", self.audio_path,
            "-af", f"volume={volume}",
            "-ar", str(self.sr),
            "-ac", str(self.ch),
            "-c:a", "pcm_s16le",
            self.temp_path
        ]
        self._process_and_replace(cmd)

    def export(self, out_path: str):
        """导出音频到目标路径（带软限幅）"""
        self._normalize(self.audio_path)
        # 优先用 os.replace(原子操作);跨文件系统时改为先 copyfile 再 os.replace
        try:
            os.replace(self.audio_path, out_path)
        except OSError:
            # 跨文件系统:先 copyfile 到目标同目录的临时文件,再 os.replace 原子替换
            target_dir = os.path.dirname(os.path.abspath(out_path)) or "."
            fd, tmp_path = tempfile.mkstemp(prefix=".svc_export_", dir=target_dir)
            os.close(fd)
            try:
                shutil.copyfile(self.audio_path, tmp_path)
                os.replace(tmp_path, out_path)
            finally:
                with contextlib.suppress(FileNotFoundError, OSError):
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
            with contextlib.suppress(FileNotFoundError, OSError):
                os.remove(self.audio_path)
        return out_path

import json
import os
import re
import shutil
import tempfile
import zipfile
from typing import List, Tuple, Optional

from sqlalchemy import Sequence

from app.core.audio_engin import AudioProcessor
from app.core.path_security import safe_extract_zip, validate_path_within_root
from app.dto.voice_dto import VoiceAudioProcessDTO
from app.entity.voice_entity import VoiceEntity
from app.models.po import MultiEmotionVoicePO, VoicePO
from app.repositories.multi_emotion_voice_repository import MultiEmotionVoiceRepository
from app.repositories.voice_repository import VoiceRepository


# ===== 业务异常 =====
class VoiceServiceError(Exception):
    """音色服务基础异常"""


class VoiceNotFoundError(VoiceServiceError):
    """音色不存在"""

    def __init__(self, voice_id: int = None, message: str = None):
        self.voice_id = voice_id
        super().__init__(message or f"音色不存在(id={voice_id})")


class VoiceAlreadyExistsError(VoiceServiceError):
    """音色名称已存在"""

    def __init__(self, name: str, message: str = None):
        self.name = name
        super().__init__(message or f"音色名称 '{name}' 已存在")


class VoiceConflictError(VoiceServiceError):
    """音色字段冲突(如试图修改 tts_provider_id)"""


def sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符,防止 Windows/Unix 下的路径问题和非法字符。

    保留中文、字母、数字、下划线、连字符;其他字符替换为下划线。
    """
    if not name:
        return "unnamed"
    # 移除路径分隔符和控制字符
    name = name.replace(os.sep, "_").replace("/", "_").replace("\\", "_")
    # 替换 Windows 非法字符: < > : " / \ | ? *
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    # 移除开头结尾的点和空格(Windows 限制)
    name = name.strip(". ")
    # 限制长度,避免文件系统限制
    if len(name) > 200:
        name = name[:200]
    return name if name else "unnamed"


def _po_to_entity(po: VoicePO) -> VoiceEntity:
    """PO 转 Entity,过滤 SQLAlchemy 内部字段"""
    data = {k: v for k, v in po.__dict__.items() if not k.startswith("_")}
    return VoiceEntity(**data)


def _entity_to_po_data(entity: VoiceEntity) -> dict:
    """Entity 转 PO 数据,过滤 None 值以避免覆盖数据库 default"""
    return {k: v for k, v in entity.__dict__.items() if v is not None}


def _validate_user_path(path: str, field_name: str = "路径") -> None:
    """校验用户可控路径:必须为绝对路径且不包含 .. 段,防止穿越任意目录。"""
    if not path or not os.path.isabs(path):
        raise ValueError(f"{field_name}必须为绝对路径")
    if ".." in path.replace("\\", "/").split("/"):
        raise ValueError(f"{field_name}不允许包含 ..")


class VoiceService:

    def __init__(self, repository: VoiceRepository, multi_emotion_voice_repository: MultiEmotionVoiceRepository):
        """注入 repository"""
        self.repository = repository
        self.multi_emotion_voice_repository = multi_emotion_voice_repository
        # 共享同一个 db session,用于跨 repository 的事务管理
        self.db = repository.db

    def create_voice(self, entity: VoiceEntity) -> VoiceEntity:
        """创建新音色
        - 检查同名音色是否存在,存在则抛 VoiceAlreadyExistsError
        - 调用 repository.create 插入数据库
        """
        voice = self.repository.get_by_name(entity.name, entity.tts_provider_id)
        if voice:
            raise VoiceAlreadyExistsError(entity.name)
        # 过滤 None 避免覆盖数据库 default(如 created_at/updated_at)
        po = VoicePO(**_entity_to_po_data(entity))
        res = self.repository.create(po)
        return _po_to_entity(res)

    def get_voice(self, voice_id: int) -> Optional[VoiceEntity]:
        """根据 ID 查询音色,不存在返回 None"""
        po = self.repository.get_by_id(voice_id)
        if not po:
            return None
        return _po_to_entity(po)

    def get_all_voices(self, tts_provider_id: int) -> Sequence[VoiceEntity]:
        """获取所有音色列表"""
        pos = self.repository.get_all(tts_provider_id)
        return [_po_to_entity(po) for po in pos]

    def update_voice(self, voice_id: int, data: dict) -> VoiceEntity:
        """更新音色
        - 可以只更新部分字段
        - 检查同名冲突
        - 检查 tts_provider_id 不能改变
        - 失败时抛出对应业务异常,便于路由层区分
        - 不在路由层重复查询,统一在此处校验
        """
        # 使用 .get() 避免 KeyError,缺失时返回 None
        name = data.get("name")
        tts_provider_id = data.get("tts_provider_id")

        po = self.repository.get_by_id(voice_id)
        if not po:
            raise VoiceNotFoundError(voice_id)

        # 防止改变 tts_provider_id
        if tts_provider_id is not None and po.tts_provider_id != tts_provider_id:
            raise VoiceConflictError("不允许修改音色所属的 TTS 供应商")

        # 检查同名冲突(仅当 name 存在时)
        if name:
            existing = self.repository.get_by_name(name, po.tts_provider_id)
            if existing and existing.id != voice_id:
                raise VoiceAlreadyExistsError(name)

        updated = self.repository.update(voice_id, data)
        return _po_to_entity(updated)

    def delete_voice(self, voice_id: int) -> bool:
        """删除音色,需要保证事务
        - 同时删除音色记录和关联的多情绪音色记录
        - 任一失败则回滚,保证数据一致性
        - 数据库提交成功后清理物理文件(失败不影响删除结果)
        """
        voice = self.db.get(VoicePO, voice_id)
        if not voice:
            return False
        reference_path = voice.reference_path
        try:
            # 先删除关联的多情绪音色
            self.db.query(MultiEmotionVoicePO).filter(
                MultiEmotionVoicePO.voice_id == voice_id
            ).delete(synchronize_session=False)
            # 再删除音色本身
            self.db.delete(voice)
            # 统一提交,保证原子性
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        # 提交成功后清理物理文件(失败不影响删除成功,仅记录日志)
        if reference_path:
            try:
                if os.path.exists(reference_path):
                    os.remove(reference_path)
            except OSError:
                # 文件清理失败不影响删除结果
                pass
        return True

    def export_voices(self, tts_provider_id: int, export_path: str, ids: List[int] | None = None) -> str:
        """导出音色库到zip文件
        - 获取所有音色
        - 将音色信息和对应的音频文件打包到zip
        - 返回zip文件路径
        """
        # 校验导出路径安全性:必须为绝对路径且不包含 ..
        _validate_user_path(export_path, "导出路径")

        if ids is None:
            voices = self.get_all_voices(tts_provider_id)
        else:
            pos = self.repository.get_by_ids(tts_provider_id, ids)
            voices = [_po_to_entity(po) for po in pos]
        if not voices:
            raise ValueError("没有可导出的音色")

        # 确保导出目录存在
        os.makedirs(os.path.dirname(export_path) if os.path.dirname(export_path) else ".", exist_ok=True)

        # 创建zip文件
        with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 准备音色元数据
            voices_metadata = []

            for voice in voices:
                voice_data = {
                    "name": voice.name,
                    "description": voice.description,
                    "is_multi_emotion": voice.is_multi_emotion,
                    "reference_file": None
                }

                # 如果有参考音频文件，添加到zip
                if voice.reference_path and os.path.exists(voice.reference_path):
                    # 保持原文件名
                    file_name = os.path.basename(voice.reference_path)
                    # 使用音色名称作为子目录，避免文件名冲突
                    archive_path = f"voices/{voice.name}/{file_name}"
                    zipf.write(voice.reference_path, archive_path)
                    voice_data["reference_file"] = archive_path

                voices_metadata.append(voice_data)

            # 写入元数据文件
            metadata_json = json.dumps(voices_metadata, ensure_ascii=False, indent=2)
            zipf.writestr("voices_metadata.json", metadata_json)

        return export_path

    def import_voices(self, tts_provider_id: int, zip_path: str, target_dir: str) -> Tuple[int, int, List[str]]:
        """从zip文件导入音色库
        - 解压zip文件
        - 将音频文件复制到指定目录
        - 添加音色到数据库（跳过重名的）
        - 返回: (成功数量, 跳过数量, 跳过的音色名称列表)
        - 整体作为一个事务,失败则回滚数据库并清理已复制的文件
        """
        if not os.path.exists(zip_path):
            raise FileNotFoundError(f"zip文件不存在: {zip_path}")

        # 校验目标目录安全性:必须为绝对路径且不包含 ..
        _validate_user_path(target_dir, "目标目录")

        # 确保目标目录存在
        os.makedirs(target_dir, exist_ok=True)

        success_count = 0
        skipped_count = 0
        skipped_names = []
        copied_files = []  # 用于失败时清理

        # 创建临时目录解压
        with tempfile.TemporaryDirectory() as temp_dir:
            # 安全解压:先校验所有成员路径,防止 Zip Slip
            safe_extract_zip(zip_path, temp_dir)

            # 读取元数据
            metadata_path = os.path.join(temp_dir, "voices_metadata.json")
            if not os.path.exists(metadata_path):
                raise ValueError("无效的音色库文件：缺少voices_metadata.json")

            with open(metadata_path, 'r', encoding='utf-8') as f:
                voices_metadata = json.load(f)

            try:
                for voice_data in voices_metadata:
                    # 使用 .get() 避免 KeyError,缺少 name 字段时跳过该条
                    voice_name = voice_data.get("name")
                    if not voice_name:
                        skipped_count += 1
                        continue

                    # 检查是否已存在同名音色
                    existing = self.repository.get_by_name(voice_name, tts_provider_id)
                    if existing:
                        skipped_count += 1
                        skipped_names.append(voice_name)
                        continue

                    reference_path = None

                    # 如果有参考音频文件，复制到目标目录
                    if voice_data.get("reference_file"):
                        # 校验 reference_file 路径不穿越临时目录
                        ref_file_rel = voice_data["reference_file"]
                        try:
                            source_file = validate_path_within_root(ref_file_rel, temp_dir)
                        except ValueError:
                            # 跳过恶意路径
                            skipped_count += 1
                            continue
                        if os.path.exists(source_file):
                            # 使用 sanitize 后的音色名称作为文件名,保留原扩展名
                            file_ext = os.path.splitext(source_file)[1]
                            safe_name = sanitize_filename(voice_name)
                            file_name = f"{safe_name}{file_ext}"
                            # 校验目标路径不穿越 target_dir
                            try:
                                dest_file = validate_path_within_root(file_name, target_dir)
                            except ValueError:
                                skipped_count += 1
                                continue
                            shutil.copy2(source_file, dest_file)
                            copied_files.append(dest_file)
                            reference_path = dest_file

                    # 创建音色实体(过滤 None,避免覆盖 default)
                    entity = VoiceEntity(
                        name=voice_name,
                        tts_provider_id=tts_provider_id,
                        reference_path=reference_path,
                        description=voice_data.get("description"),
                        is_multi_emotion=voice_data.get("is_multi_emotion", 0)
                    )

                    # 保存到 session(暂不提交,等循环结束统一提交,保证原子性)
                    po = VoicePO(**_entity_to_po_data(entity))
                    self.db.add(po)
                    self.db.flush()  # flush 让 po 拿到 id,但不 commit
                    success_count += 1

                # 统一提交,保证原子性
                self.db.commit()
            except Exception:
                # 失败回滚数据库
                self.db.rollback()
                # 清理已复制的文件,避免孤儿文件
                for f in copied_files:
                    try:
                        if os.path.exists(f):
                            os.remove(f)
                    except OSError:
                        pass
                raise

        return success_count, skipped_count, skipped_names

    def process_audio(self, dto: VoiceAudioProcessDTO) -> bool:
        """处理音色参考音频
        - 变速、音量调整
        - 裁剪/删除区间
        - 添加/裁剪末尾静音
        - 指定位置插入静音
        """
        audio_path = dto.audio_path
        # 校验路径安全性:必须为绝对路径,不包含 ..
        _validate_user_path(audio_path, "音频路径")

        if not os.path.exists(audio_path):
            raise FileNotFoundError(audio_path)

        with AudioProcessor(audio_path) as processor:
            start_ms = dto.start_ms
            end_ms = dto.end_ms
            speed = dto.speed
            volume = dto.volume
            current_ms = dto.current_ms
            silence_sec = dto.silence_sec

            # ---------- (1) 优先裁剪 ----------
            if start_ms is not None and end_ms is not None and end_ms > start_ms:
                processor.cut(start_ms, end_ms)

            # ---------- (2) 插入静音 ----------
            elif current_ms is not None and silence_sec is not None and silence_sec != 0:
                processor.insert_silence(current_ms, silence_sec)

            # ---------- (3) 末尾静音/裁剪 ----------
            elif current_ms is None and silence_sec is not None and silence_sec != 0:
                processor.append_silence(silence_sec)

            # ---------- (4) 音量 + 变速 ----------
            if speed != 1.0:
                processor.change_speed(speed)
            if volume != 1.0:
                processor.change_volume(volume)

        return True

    def copy_voice(self, source_voice_id: int, new_name: str, target_dir: str = None) -> VoiceEntity:
        """复制音色
        - 获取源音色信息
        - 复制音频文件到目标目录
        - 创建新音色记录
        - 返回新音色实体
        - 任一失败回滚对方操作,保证文件与数据库一致性
        """
        # 获取源音色
        source_voice = self.get_voice(source_voice_id)
        if not source_voice:
            raise VoiceNotFoundError(source_voice_id)

        # 检查新名称是否已存在
        existing = self.repository.get_by_name(new_name, source_voice.tts_provider_id)
        if existing:
            raise VoiceAlreadyExistsError(new_name)

        new_reference_path = None
        file_copied = False

        # 处理音频文件复制
        if source_voice.reference_path and os.path.exists(source_voice.reference_path):
            # 确定目标目录
            if target_dir and target_dir.strip():
                dest_dir = target_dir.strip()
                # 校验目标目录安全性
                _validate_user_path(dest_dir, "目标目录")
            else:
                # 使用源音频所在目录
                dest_dir = os.path.dirname(source_voice.reference_path)

            # 确保目标目录存在
            os.makedirs(dest_dir, exist_ok=True)

            # 获取源文件扩展名
            file_ext = os.path.splitext(source_voice.reference_path)[1]
            # 使用 sanitize 后的新音色名作为文件名
            safe_name = sanitize_filename(new_name)
            new_file_name = f"{safe_name}{file_ext}"
            new_reference_path = os.path.join(dest_dir, new_file_name)

            # 复制文件
            shutil.copy2(source_voice.reference_path, new_reference_path)
            file_copied = True

        # 创建新音色实体(过滤 None,避免覆盖 default)
        new_entity = VoiceEntity(
            name=new_name,
            tts_provider_id=source_voice.tts_provider_id,
            reference_path=new_reference_path,
            description=source_voice.description,
            is_multi_emotion=source_voice.is_multi_emotion
        )
        # 保存到数据库,失败时清理已复制的文件,避免孤儿文件
        po = VoicePO(**_entity_to_po_data(new_entity))
        try:
            res = self.repository.create(po)
        except Exception:
            if file_copied and new_reference_path and os.path.exists(new_reference_path):
                try:
                    os.remove(new_reference_path)
                except OSError:
                    pass
            raise

        # 返回新建的音色实体
        return _po_to_entity(res)

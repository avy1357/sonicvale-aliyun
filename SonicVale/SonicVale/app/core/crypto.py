# app/core/crypto.py
"""敏感字段对称加密工具

使用 Fernet (AES-128-CBC + HMAC-SHA256) 对 LLM/TTS Provider 的
api_key、x_api_key、access_key_id、access_key_secret 等凭据做对称加密。

主密钥存储于用户目录 ~/SonicVale/secret.key, 首次运行自动生成。
Repository 层在写库前加密、读出后解密, 业务层无感知。
"""
import os
import base64
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import getConfigPath

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 敏感字段白名单
# ---------------------------------------------------------------------------
LLM_PROVIDER_SECRET_FIELDS: tuple = ("api_key",)
TTS_PROVIDER_SECRET_FIELDS: tuple = (
    "api_key",
    "x_api_key",
    "access_key_id",
    "access_key_secret",
)

# ---------------------------------------------------------------------------
# 主密钥管理
# ---------------------------------------------------------------------------
_KEY_FILE = os.path.join(getConfigPath(), "secret.key")
_fernet: "Fernet | None" = None


def _get_fernet() -> Fernet:
    """获取全局 Fernet 实例, 首次调用时加载/生成主密钥"""
    global _fernet
    if _fernet is not None:
        return _fernet

    if os.path.exists(_KEY_FILE):
        with open(_KEY_FILE, "rb") as f:
            key = f.read().strip()
        try:
            _fernet = Fernet(key)
            return _fernet
        except (ValueError, base64.binascii.Error):
            logger.warning("主密钥文件损坏, 重新生成: %s", _KEY_FILE)

    # 生成新密钥
    key = Fernet.generate_key()
    # 以仅属主可读写权限保存 (0600)
    fd = os.open(_KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, key)
    finally:
        os.close(fd)
    _fernet = Fernet(key)
    logger.info("已生成新主密钥: %s", _KEY_FILE)
    return _fernet


def _encrypt_value(plain: str) -> str:
    """加密单个字符串, 返回带前缀的密文"""
    if plain is None:
        return None
    if not isinstance(plain, str):
        plain = str(plain)
    # 空字符串不加密, 避免浪费
    if plain == "":
        return ""
    token = _get_fernet().encrypt(plain.encode("utf-8"))
    return "ENC:" + token.decode("ascii")


def _decrypt_value(cipher: str) -> str:
    """解密单个字符串, 非密文原样返回"""
    if cipher is None:
        return None
    if not isinstance(cipher, str):
        return cipher
    if not cipher.startswith("ENC:"):
        # 明文兼容: 历史数据未加密时直接返回
        return cipher
    try:
        token = cipher[4:].encode("ascii")
        return _get_fernet().decrypt(token).decode("utf-8")
    except Exception as e:
        logger.warning("解密失败, 返回原值: %s", e)
        return cipher


# ---------------------------------------------------------------------------
# PO 对象级加解密 (原地修改并返回)
# ---------------------------------------------------------------------------
def encrypt_provider_fields(po, fields: tuple):
    """对 PO 对象的指定字段做原地加密, 返回 po 本身"""
    if po is None:
        return None
    for field in fields:
        value = getattr(po, field, None)
        if value is not None and value != "" and not (isinstance(value, str) and value.startswith("ENC:")):
            setattr(po, field, _encrypt_value(value))
    return po


def decrypt_provider_fields(po, fields: tuple):
    """对 PO 对象的指定字段做原地解密, 返回 po 本身"""
    if po is None:
        return None
    for field in fields:
        value = getattr(po, field, None)
        if value is not None and isinstance(value, str) and value.startswith("ENC:"):
            setattr(po, field, _decrypt_value(value))
    return po


def encrypt_provider_dict(data: dict, fields: tuple):
    """对 dict 中的敏感字段做原地加密 (仅加密存在的 key), 返回 data 本身"""
    if not data:
        return data
    for field in fields:
        if field in data and data[field] is not None and data[field] != "":
            value = data[field]
            if not (isinstance(value, str) and value.startswith("ENC:")):
                data[field] = _encrypt_value(value)
    return data

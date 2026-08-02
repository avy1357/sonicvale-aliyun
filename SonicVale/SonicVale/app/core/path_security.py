"""路径安全校验工具

提供路径穿越防护、Zip Slip 防护等功能。
所有涉及用户可控路径的文件操作都应经过此模块校验。
"""
import os
from typing import List


def validate_path_within_root(path: str, root: str) -> str:
    """校验路径必须位于指定根目录下,防止路径穿越。

    Args:
        path: 待校验的路径(可为相对/绝对路径)
        root: 允许的根目录(绝对路径)

    Returns:
        规范化后的绝对路径

    Raises:
        ValueError: 路径不在允许的根目录下,或路径非法
    """
    if not path or not root:
        raise ValueError("路径和根目录不能为空")

    # 规范化根目录
    root_real = os.path.realpath(root)

    # 拼接并规范化目标路径
    # 如果 path 是绝对路径,os.path.join 会忽略 root,因此先判断
    target = os.path.join(root_real, path) if not os.path.isabs(path) else path
    target_real = os.path.realpath(target)

    # 校验目标路径必须以根目录为前缀
    # 使用 normcase 统一大小写(Windows 下盘符大小写不敏感)
    root_norm = os.path.normcase(root_real)
    target_norm = os.path.normcase(target_real)
    if not target_norm.startswith(root_norm + os.sep) and target_norm != root_norm:
        raise ValueError(
            f"安全限制:路径 '{path}' 超出允许的根目录范围"
        )

    return target_real


def validate_zip_members(zip_path: str, extract_root: str) -> List[str]:
    """校验 zip 文件中所有成员路径,防止 Zip Slip 攻击。

    在解压前调用此函数,拒绝包含 `..` 或以 `/` 开头的成员。

    Args:
        zip_path: zip 文件路径
        extract_root: 解压目标根目录

    Raises:
        ValueError: 发现恶意路径成员
    """
    import zipfile

    extract_root_real = os.path.realpath(extract_root)
    extract_root_norm = os.path.normcase(extract_root_real)
    malicious = []

    with zipfile.ZipFile(zip_path, 'r') as zf:
        for name in zf.namelist():
            # 拒绝绝对路径和 ..
            if name.startswith('/') or name.startswith('\\'):
                malicious.append(name)
                continue
            if '..' in name.replace('\\', '/').split('/'):
                malicious.append(name)
                continue
            # 双重校验:拼接后规范化也必须在根目录下
            # 使用 normcase 统一大小写(Windows 下盘符大小写不敏感)
            target = os.path.realpath(os.path.join(extract_root_real, name))
            target_norm = os.path.normcase(target)
            if not target_norm.startswith(extract_root_norm + os.sep) and target_norm != extract_root_norm:
                malicious.append(name)

    if malicious:
        raise ValueError(
            f"安全限制:zip 文件包含恶意路径成员: {malicious[:5]}"
        )

    return extract_root_real


def safe_extract_zip(zip_path: str, extract_root: str) -> None:
    """安全解压 zip 文件,先校验所有成员再解压。

    Args:
        zip_path: zip 文件路径
        extract_root: 解压目标根目录

    Raises:
        ValueError: 发现恶意路径成员
        FileNotFoundError: zip 文件不存在
    """
    import zipfile

    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"zip 文件不存在: {zip_path}")

    # 先校验所有成员
    validate_zip_members(zip_path, extract_root)

    # 校验通过后再解压
    os.makedirs(extract_root, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(extract_root)


# 系统关键目录黑名单(防止向系统目录写入/删除文件)
_SYSTEM_CRITICAL_DIRS = [
    # Windows
    r"c:\windows", r"c:\program files", r"c:\program files (x86)",
    r"c:\programdata", r"c:\windows\system32", r"c:\$recycle.bin",
    # Unix
    "/etc", "/usr", "/bin", "/sbin", "/boot", "/lib", "/lib64", "/dev", "/proc", "/sys",
    # macOS
    "/system", "/library", "/applications",
]


def assert_path_not_system_critical(path: str) -> None:
    """校验路径不指向系统关键目录,防止向系统目录写入/删除文件。

    Args:
        path: 待校验的路径

    Raises:
        ValueError: 路径指向系统关键目录
    """
    if not path:
        return
    real = os.path.realpath(path)
    norm = os.path.normcase(real)
    for critical in _SYSTEM_CRITICAL_DIRS:
        c_norm = os.path.normcase(critical)
        if norm == c_norm or norm.startswith(c_norm + os.sep):
            raise ValueError(
                f"安全限制:路径 '{path}' 指向系统关键目录,禁止操作"
            )

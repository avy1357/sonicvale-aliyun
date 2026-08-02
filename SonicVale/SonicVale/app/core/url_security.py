"""URL 安全校验工具(SSRF 防护)

用于校验用户输入的 URL 是否指向公网地址,防止 SSRF 攻击。
默认拒绝:
- 非 http/https 协议(file://, gopher://, ftp:// 等)
- 回环地址 127.0.0.0/8, ::1
- 私有地址 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
- 链路本地 169.254.0.0/16
- 多播/保留地址 0.0.0.0/8, 224.0.0.0/4
- 主机名为空或 'localhost'

可通过环境变量 SVC_ALLOW_PRIVATE_URL=true 放行内网地址(仅用于内网部署场景)。
"""
import ipaddress
import logging
import os
import socket
from typing import Optional
from urllib.parse import urlparse


# 是否允许内网地址(默认 False,仅公网)
_ALLOW_PRIVATE = os.getenv("SVC_ALLOW_PRIVATE_URL", "").lower() in ("1", "true", "yes")


def _is_internal_ip(ip_str: str) -> bool:
    """判断 IP 字符串是否为内网/回环/保留地址"""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # 非 IP 视为不安全

    # IPv6 回环
    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True
    return False


def validate_public_url(url: str, allow_private: Optional[bool] = None) -> str:
    """校验 URL 必须指向公网地址,防止 SSRF。

    注意:本函数存在 DNS rebinding 理论风险(DNS 解析与实际请求之间可能被切换),
    且 socket.getaddrinfo 为阻塞调用。异步上下文应通过 run_in_executor 包装。
    生产环境建议改用 IP 直连方式。

    Args:
        url: 待校验的 URL
        allow_private: 是否允许内网地址。None 时使用环境变量 SVC_ALLOW_PRIVATE_URL

    Returns:
        原始 URL(校验通过)

    Raises:
        ValueError: URL 非法或指向内网/回环地址
    """
    # 注意:本函数存在 DNS rebinding 理论风险,且 socket.getaddrinfo 为阻塞调用。
    # 异步上下文应通过 run_in_executor 包装。生产环境建议改用 IP 直连方式。
    if not url or not isinstance(url, str):
        raise ValueError("URL 不能为空")

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"URL 协议必须是 http 或 https,当前为 '{scheme}'")

    host = parsed.hostname
    if not host:
        raise ValueError("URL 缺少主机名")

    host_lower = host.lower()
    if host_lower == "localhost":
        raise ValueError("URL 主机名不能为 localhost")

    # 检查是否允许内网
    do_allow_private = _ALLOW_PRIVATE if allow_private is None else allow_private
    if do_allow_private:
        return url

    # 解析主机为 IP
    # 如果 host 本身就是 IP,直接判断
    try:
        ipaddress.ip_address(host)
    except ValueError:
        # host 不是 IP,可能是域名,继续 DNS 解析
        ip_is_literal = False
    else:
        ip_is_literal = True
        if _is_internal_ip(host):
            raise ValueError(f"URL 指向内网/回环地址,已被 SSRF 防护拒绝: {host}")
        return url

    # 域名解析为 IP 后判断
    try:
        # 使用 getaddrinfo 获取所有解析结果,任一为内网即拒绝
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise ValueError(f"URL 主机名解析失败: {host} ({e})")

    for family, _, _, _, sockaddr in infos:
        ip_str = sockaddr[0]
        # 处理 IPv6 映射的 IPv4 地址
        if ip_str.startswith("::ffff:"):
            ip_str = ip_str[7:]
        if _is_internal_ip(ip_str):
            raise ValueError(
                f"URL 主机名 '{host}' 解析到内网/回环地址 {ip_str},已被 SSRF 防护拒绝"
            )

    return url

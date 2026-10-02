"""网络请求的 TLS 验证配置。

Windows 上优先使用系统证书库（ssl.create_default_context），
这样可以兼容企业/安全软件安装的 HTTPS 根证书；
如果创建失败则回退到 httpx 默认（certifi）。
"""

from __future__ import annotations

import ssl

_context = None


def default_verify():
    """返回 httpx 的 verify 参数：系统 SSL 上下文（带缓存）。"""
    global _context
    if _context is None:
        try:
            _context = ssl.create_default_context()
        except Exception:
            _context = True
    return _context

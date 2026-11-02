"""WebUI 认证（§01.2.5）—— 只做一件事：**开了局域网就真的要求密码**。

为什么不是 HTTP Basic 中间件就完事
--------------------------------
两件事必须同时成立，缺一个都只是"看起来有密码"：

1. **绑定与认证联动**：``allow_lan=true`` 时 API 必须绑到非回环地址，否则局域网
   根本连不上；反过来，只要绑到了非回环地址，就必须要求密码 —— 不能靠用户
   记得把两个开关都打开。
2. **WebSocket 也过同一道门**：面板的实时通道走 ``/ws/ui``，它和 REST 是同一条
   数据面。只保护 REST 等于把日志 / 任务事件留在门外晾着。

这里用纯 ASGI 中间件（不是 ``BaseHTTPMiddleware``）：后者只覆盖 HTTP，WebSocket
握手会直接穿过去。
"""

from __future__ import annotations

import base64
import binascii
import hmac
from dataclasses import dataclass
from typing import Final

from starlette.types import ASGIApp, Receive, Scope, Send

__all__ = ["LOOPBACK_HOSTS", "WebUiAuth", "is_loopback_host"]

LOOPBACK_HOSTS: Final[frozenset[str]] = frozenset({"127.0.0.1", "::1", "localhost"})

#: 免认证的健康检查：它只回进程状态，不碰库、不碰密钥。
_PUBLIC_PATHS: Final[frozenset[str]] = frozenset({"/api/v1/health"})

#: 401 响应体：错误码与其它接口同构（``ok=false`` + ``error.code``）。
_AUTH_BODY: Final[bytes] = (
    b'{"ok":false,"error":{"code":"AUTH_REQUIRED","message":"\\u9700\\u8981 WebUI \\u5bc6\\u7801"}}'
)


def is_loopback_host(host: str) -> bool:
    """``localhost`` / ``127.0.0.1`` / ``::1`` 视为回环。"""
    return host.strip().strip("[]").casefold() in LOOPBACK_HOSTS


@dataclass(frozen=True, slots=True)
class WebUiAuth:
    """一次启动周期内的认证策略（密码来自 ``config/secrets.yaml`` 或环境变量）。"""

    required: bool
    password: str | None = None

    @classmethod
    def from_config(cls, *, allow_lan: bool, host: str, password: str | None) -> WebUiAuth:
        required = allow_lan or not is_loopback_host(host)
        return cls(required=required, password=password)

    def authorized(self, header: str | None) -> bool:
        """``Authorization: Basic <b64>`` 是否带对了密码。

        用户名不参与判断：这是给"自己家局域网"用的门闩，不是多用户系统。
        """
        if not self.required:
            return True
        if not self.password or not header:
            return False
        scheme, _, payload = header.partition(" ")
        if scheme.casefold() != "basic" or not payload:
            return False
        try:
            decoded = base64.b64decode(payload, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return False
        _, _, supplied = decoded.partition(":")
        # 常量时间比较：密码比较不该按字符提前返回
        return hmac.compare_digest(supplied, self.password)


class WebUiAuthMiddleware:
    """纯 ASGI 中间件：HTTP 与 WebSocket 共用一道门。"""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        auth = getattr(scope["app"].state, "web_auth", None)
        if auth is None or not auth.required:
            await self._app(scope, receive, send)
            return

        path = scope.get("path", "")
        if scope["type"] == "http" and path in _PUBLIC_PATHS:
            await self._app(scope, receive, send)
            return

        header = _header(scope, b"authorization")
        if auth.authorized(header):
            await self._app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return

        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"www-authenticate", b'Basic realm="studio", charset="UTF-8"'),
                    (b"content-type", b"application/json; charset=utf-8"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _AUTH_BODY})


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return str(value.decode("latin-1"))
    return None

"""WebUI 认证（§01.2.5）—— 密码必须**真的**参与请求校验。"""

from __future__ import annotations

import base64

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from studio.app.middleware.auth import WebUiAuth, WebUiAuthMiddleware, is_loopback_host


def _basic(password: str, user: str = "studio") -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def test_loopback_hosts_are_not_required_to_have_a_password() -> None:
    assert is_loopback_host("127.0.0.1")
    assert is_loopback_host("localhost")
    assert is_loopback_host("::1")
    auth = WebUiAuth.from_config(allow_lan=False, host="127.0.0.1", password=None)
    assert auth.required is False
    assert auth.authorized(None) is True


@pytest.mark.parametrize(("allow_lan", "host"), [(True, "127.0.0.1"), (False, "0.0.0.0")])
def test_lan_or_non_loopback_requires_a_password(allow_lan: bool, host: str) -> None:
    auth = WebUiAuth.from_config(allow_lan=allow_lan, host=host, password="s3cret")
    assert auth.required is True
    assert auth.authorized(None) is False
    assert auth.authorized(_basic("s3cret")["Authorization"]) is True
    assert auth.authorized(_basic("wrong")["Authorization"]) is False
    assert auth.authorized("Basic !!!") is False


def _guarded_app() -> FastAPI:
    application = FastAPI()
    application.add_middleware(WebUiAuthMiddleware)
    application.state.web_auth = WebUiAuth(required=True, password="s3cret")

    @application.get("/api/v1/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @application.get("/api/v1/private")
    def private() -> dict[str, bool]:
        return {"ok": True}

    return application


def test_http_requests_need_basic_auth_but_health_is_public() -> None:
    client = TestClient(_guarded_app())
    public = client.get("/api/v1/health")
    assert public.status_code == 200

    denied = client.get("/api/v1/private")
    assert denied.status_code == 401
    assert denied.headers["www-authenticate"].startswith("Basic ")

    allowed = client.get("/api/v1/private", headers=_basic("s3cret"))
    assert allowed.status_code == 200


def test_websocket_handshake_is_guarded_too() -> None:
    application = _guarded_app()

    @application.websocket("/ws/ui")
    async def ws(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.close()

    client = TestClient(application)
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws/ui"):
        pass

    with client.websocket_connect("/ws/ui", headers=_basic("s3cret")) as socket:
        socket.close()

"""重新生成 Web 侧契约（T4.1 · §02.2）。

用法（**不再依赖 env.ps1**；路径固定按仓库根推导，保证 CI 与本地渲染同一份契约）::

    uv run python scripts/dump_web_contracts.py          # 重新生成
    uv run python scripts/dump_web_contracts.py --check   # 只比对，不写盘（漂移 ⇒ 退出码 1）

生成物两份，都**入库**（漂移要在 diff 里看得见）::

    web/openapi.json            FastAPI 的 OpenAPI 3.1 快照
    web/src/ws/events.ts        WS 协议常量 + 信封 + 日志行（`ws/protocol.py` 是真相源）

生成完之后还要跑 `npm run gen:api`（把 openapi.json 变成 TS 类型）——
两步分开是因为前者是 Python 的活，后者是 node 的活。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fastapi import FastAPI

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from studio.app.main import create_app  # noqa: E402
from studio.app.webcontracts import (  # noqa: E402
    EVENTS_TS_RELATIVE,
    OPENAPI_JSON_RELATIVE,
    render_events_ts,
    render_openapi_json,
    write_web_contracts,
)
from studio.core.paths import StudioPaths  # noqa: E402

WEB_DIR = REPO_ROOT / "web"


def _app_for_contracts() -> FastAPI:
    """用**仓库内**路径造 app，不依赖调用方有没有 dot-source ``env.ps1``。

    CI 与本地必须渲染出同一份契约：从环境变量推断路径会让「没跑 env.ps1」的机器
    直接失败（GitHub Actions 就是这样），而不是"契约漂移"。顺手把运行期目录建好，
    免得 sqlite 因为 ``data/`` 不存在而打不开。
    """
    paths = StudioPaths(home=REPO_ROOT, data_dir=REPO_ROOT / "data")
    paths.ensure_runtime_dirs()
    return create_app(paths=paths)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 / 校验 Web 侧契约（T4.1）")
    parser.add_argument("--check", action="store_true", help="只比对不写盘（漂移 ⇒ 退出码 1）")
    args = parser.parse_args()

    if not args.check:
        written = write_web_contracts(WEB_DIR, app=_app_for_contracts())
        for path in written:
            print(f"[gen] {path.relative_to(REPO_ROOT)}")
        print("[gen] 下一步：cd web && npm run gen:api")
        return 0

    app = _app_for_contracts()
    drift: list[str] = []
    for relative, expected in (
        (OPENAPI_JSON_RELATIVE, render_openapi_json(app)),
        (EVENTS_TS_RELATIVE, render_events_ts()),
    ):
        target = WEB_DIR / relative
        actual = target.read_text(encoding="utf-8") if target.is_file() else None
        if actual != expected:
            drift.append(relative)
    if drift:
        print("[check] 生成物已漂移：" + ", ".join(drift))
        print("[check] 修复：uv run python scripts/dump_web_contracts.py")
        return 1
    print("[check] Web 契约与后端一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Changelog

本文件记录**可观察到的行为变化**（配置契约、安全边界、门禁与依赖）。
格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

### Added

- WebUI 认证中间件（`studio.app.middleware.auth`）：`allow_lan=true` 或绑定到非回环地址时
  **强制 Basic 认证**，REST 与 WebSocket（`/ws/ui`）共用同一道门；只有 `/api/v1/health` 免认证。
- `allow_lan=true` 时 `studio serve` 真正绑定 `0.0.0.0`（此前只改配置、不改绑定地址）。
- CI（`.github/workflows/ci.yml`）：ruff format / ruff check / Web 契约 / mypy / pytest + 前端
  typecheck / test / build / 体积门禁。
- pre-commit（`.pre-commit-config.yaml`）：提交前只跑 ruff，完整门禁仍是 `.\tasks.ps1 check`。
- `.\tasks.ps1 cov`：带 `pytest-cov` 的覆盖率任务。
- `LICENSE`（MIT）。

### Changed

- **R1 单盘豁免**：仓库本身在系统盘时，仓库内路径（`models/`、`data/caches/`）不再被判成
  「写爆系统盘」。仓库外的绝对路径仍按 R1 拒绝；`tts.model.dir` 仍拒绝 `C:\models` 这类手填绝对路径。
- `scripts/env.ps1` 与 `.env.example` 默认值改为仓库内 `data/caches/*`，不再假设存在 `D:` 盘；
  有独立数据盘的机器用 `.env` 覆盖即可。
- `doctor` 的磁盘门禁阈值改为优先读 `config/app.yaml disk_gate`，与 `MetricsService` 同一组数。
- `doctor` 的 uv 缓存检查、磁盘门禁文案适配单盘机器。
- README 本机环境基线更新为实测值（Ryzen AI 9 H 365 / 单盘 C: / 外部 FFmpeg / Python 3.12 + 3.11 双环境）。
- `tts/uv.lock` 纳入版本控制（TTS 依赖必须可复现）。
- 项目根 `uv.lock` 同步 `pytest-cov` / `coverage`。
- 根目录垃圾文件 `-`（测试假件把量宽输出 `-` 当成文件写出来的）已删除，并从源头修掉。

### Fixed

- `tts.model.dir = models/...` 在单盘机器上触发的 `CONFIG_INVALID`（历史用例大面积红）。
- `resolve_out_path` 未拦截 Windows 盘符：`C:/evil.wav` 在 `PurePosixPath` 下被当成相对路径。
- `tests/integration/test_topics_api.py` 的选题脚本命中「画面词」闸门，导致固定丢 3 条；
  换成与账号定位一致的民生选题。
- `tests/integration/test_gc_cli.py` 依赖真实当前时间，跨天即红；改用 `freeze_time`。
- `tests/unit/render/*` 的贴纸路径类型错误（`str` → `Path`）。
- `web/src/stores/persona.test.ts` 缺 `speaker_names` 夹具（vue-tsc 2 错 + vitest 14 败）。
- 脚本在 GBK 控制台输出 emoji 时的 `UnicodeEncodeError`（`dump_web_contracts.py` /
  `ingest_voice_src.py`）。
- 测试的 ffmpeg 探测与生产 `STUDIO_FFMPEG_BIN` / `STUDIO_FFPROBE_BIN` 不同步，导致整片用例被跳过。

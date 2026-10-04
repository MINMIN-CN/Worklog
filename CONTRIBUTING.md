# 贡献指南

**简体中文** | [English](#english)

感谢你愿意为「工作小记」出一份力！无论是反馈 Bug、提功能建议，还是直接提交代码，都欢迎。

## 提交 Issue

- **Bug**：使用 [Bug 反馈模板](https://github.com/MINMIN-CN/Worklog/issues/new?template=bug_report.yml)，附上版本号、Windows 版本和复现步骤。如果应用启动失败，安装目录下的 `worklog_error.log` 很有帮助。
- **功能建议**：使用 [功能建议模板](https://github.com/MINMIN-CN/Worklog/issues/new?template=feature_request.yml)。
- 提问前可以先看看 [README](README.md)，安装、配置 AI、常见问题都在里面。

## 开发环境

- Windows 10 / 11
- Python 3.11+，推荐使用 [uv](https://docs.astral.sh/uv/)
- 大部分测试不需要联网（模型接口有 mock）

```bat
uv sync          :: 安装依赖
run_debug.bat    :: 带控制台启动，方便看日志
```

或者手动：

```bat
uv run python -m worklog
```

## 运行测试

提交 PR 前请确保相关测试通过：

```bat
uv run python tools/smoke_test.py        :: 核心模块 + 界面构造冒烟测试
uv run python tools/flow_test.py         :: mock 模型接口的全链路测试
uv run python tools/app_start_test.py    :: 应用启动退出测试
uv run python tools/updater_flow_test.py :: 更新下载流程测试
uv run python tools/i18n_coverage.py     :: 英文模式中文残留检查
```

## 代码约定

- 保持与现有代码一致的结构、命名和风格。
- **新增界面中文文案时，必须同步在 `worklog/_catalog_en.py` 补充英文翻译**，键名与中文原文完全一致，否则英文模式会残留中文（`i18n_coverage.py` 会检查）。
- AI 提示词：中文在 `worklog/analyze.py`、`worklog/reporting.py`；英文版本在 `worklog/prompts_en.py`、`worklog/templates_en.py`。
- 不要提交 `data/`、`dist/`、日志，或任何 API Key、真实工作记录等个人数据。

## 提交 PR

1. 从 `main` 切出分支，例如 `fix/report-empty`。
2. 一个 PR 只做一件事，描述里写清「改了什么、为什么」。
3. 涉及界面的改动请附截图。
4. 版本号、更新清单（`update/manifest.json`）与发布由维护者统一处理。

---

## English

Thanks for helping improve WorkLog! Bug reports, feature ideas and pull requests are all welcome.

### Issues

- **Bugs**: use the [bug report template](https://github.com/MINMIN-CN/Worklog/issues/new?template=bug_report.yml) and include the app version, Windows version and reproduction steps.
- **Features**: use the [feature request template](https://github.com/MINMIN-CN/Worklog/issues/new?template=feature_request.yml).
- Check the [README](README.md) (and [README.en.md](README.en.md)) first — setup and FAQ live there.

### Development

- Windows 10/11, Python 3.11+, [uv](https://docs.astral.sh/uv/) recommended.
- `uv sync` to install dependencies, `uv run python -m worklog` to run.

### Tests

```bat
uv run python tools/smoke_test.py
uv run python tools/flow_test.py
uv run python tools/app_start_test.py
uv run python tools/updater_flow_test.py
uv run python tools/i18n_coverage.py
```

### Conventions

- Keep the existing structure, naming and style.
- **When adding Chinese UI strings, add the English translation to `worklog/_catalog_en.py`** — keys must match the Chinese text exactly, otherwise English mode leaks Chinese.
- Never commit `data/`, `dist/`, logs, API keys or personal data.

### Pull requests

- Branch from `main`, one change per PR, explain what and why.
- Include screenshots for UI changes.
- The maintainer handles version bumps, the update manifest and releases.

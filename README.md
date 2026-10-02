# 工作小记（WorkLog）

**简体中文** | [English](README.en.md)

本地优先的 AI 工作记录与日报助手，Windows 桌面版。参考 B 站「小黑日报助手」的核心工作流自己实现：

> 自动记录工作轨迹 → AI 理解内容 → 生成日报 / 周报 / 月报 → 提取待办 → 接入自己的 Agent

截图只在内存中用于一次 AI 分析，**分析完立即销毁，不落盘**；工作记录、报告、待办全部保存在本机 `data/` 目录。

## 功能一览

| 模块 | 说明 |
| --- | --- |
| 自动记录 | 按间隔截屏，同时记录前台应用与窗口标题；画面没变化时自动合并，不浪费 AI 调用 |
| AI 理解 | 多模态模型识别内容，自动分类（开发/会议/沟通/文档…）、生成摘要、项目与标签；内置隐私脱敏提示词 |
| 时间线 | 按天查看工作记录，支持编辑、删除、手动补录、对未分析的记录做文本补分析 |
| 统计 | 专注时长、应用使用排行、分类分布、周 × 小时热力图、高频标签 |
| 报告 | 一键生成日报/周报/月报，内置 4 套模板，支持补充要求，生成后自动存库并导出 Markdown |
| 待办 | 手动添加或让 AI 从某天时间线中提取，支持截止日期与完成状态 |
| 本地 Agent API | 127.0.0.1 上的 HTTP 接口，可读时间线/统计/报告，也可写入记录和待办 |
| 系统托盘 | 关闭窗口自动最小化到托盘继续记录，可随时暂停/继续/立即记录 |
| 语言 | 简体中文 / English，默认跟随系统，可在设置中切换（重启生效）；安装向导同样自动匹配系统语言 |

## 快速开始

环境已装好 `uv`，在本目录执行：

```bat
install.bat     :: 首次安装依赖（已执行过可跳过）
run.bat         :: 启动应用（无控制台窗口）
run_debug.bat   :: 排查问题用，带控制台日志
```

或者手动：

```bat
uv sync
uv run python -m worklog
```

首次启动后，打开左侧「设置」填入 AI 接口，保存即可。没有配置 Key 时也会正常记录（只有应用名和窗口标题），配置后可对历史记录点「重新分析未分析」。

## 配置 AI 接口（傻瓜式）

打开「设置 → AI 模型接口」，三步完成：

1. **服务商**下拉框选一个（内置 DeepSeek、通义千问、智谱 GLM、硅基流动、Kimi、火山方舟、腾讯混元、百度千帆、OpenAI、本地 Ollama）
2. 粘贴该服务商的 **API Key**
3. 点「**测试连接**」（会分别检查文本模型和视觉模型），通过后点「保存设置」

选好服务商后接口地址和模型名会自动填好，一般不用改。需要自定义接口或模型名时，展开「**高级设置**」手动修改即可。首次打开还会在「今日」页看到「去设置」的提示按钮。

> 💡 **DeepSeek 已原生支持图片输入**（`deepseek-flash`，2026-09 起），本工具默认预设就是它：国内直连、便宜、无需代理。
> 💡 模型名可能随服务商更新，如果测试提示「模型不存在」，在高级设置里换成该服务商最新的模型名即可。

配置保存在数据目录的 `config.json`，也可以直接编辑。

## 使用建议

- **截屏间隔**：默认 120 秒。太短会消耗更多 AI 额度，太长会丢失细节。上班摸鱼担心额度可以先设 300 秒。
- **排除应用**：默认排除 KeePass、1Password 等密码管理器，按需添加微信、私人邮箱等敏感应用（每行一个进程名，如 `WeChat.exe`）。
- **空闲暂停**：默认离开键鼠 5 分钟后停止记录，回来自动恢复；锁屏期间也会暂停。
- **合并规则**：窗口和应用不变且画面相似时，会把时间累加到上一条记录（`×N` 表示采集次数），只有画面明显变化才会调用 AI。
- **随机启动**：安装包内勾选「开机自动启动」，或把 `run.bat` 的快捷方式放进 `shell:startup` 目录。

## 本地 Agent API

默认监听 `http://127.0.0.1:8765`（可在设置中改端口或关闭）。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| GET | `/api/timeline?date=YYYY-MM-DD` 或 `?start=&end=` | 工作时间线 |
| GET | `/api/stats?date=` 或 `?start=&end=` | 聚合统计 |
| GET | `/api/app-usage?date=` | 应用使用时长 |
| GET | `/api/todos` | 待办列表 |
| GET | `/api/reports`、`/api/reports/{id}` | 报告列表 / 详情 |
| POST | `/api/records` | 写入一条工作记录（JSON: `title`、`app`、`start_ts`…） |
| POST | `/api/todos` | 创建待办 |
| PATCH | `/api/todos/{id}` | 更新待办状态 `{"status": "done"}` |

示例：

```bat
curl "http://127.0.0.1:8765/api/timeline?date=2026-10-02"
```

这样你自己的 Agent（比如 OpenCode、Cherry Studio 等）就能直接读取工作数据，或把完成的事情写回时间线。

## 隐私说明

- 截图通过 `mss` 抓取后仅在内存中压缩、编码并发送给你自己配置的模型接口，分析结束立即释放，不写入磁盘。
- 发送给模型前，提示词强制要求脱敏：不记录人名、账号、密码、聊天原文，私密画面只保留「私密内容」标记。
- 所有结构化记录、报告、待办保存在本机 `data/worklog.db`（SQLite）。
- 排除列表命中的应用不会被截屏。
- 本地 API 只绑定 `127.0.0.1`，局域网不可访问。

## 升级与自动更新

### 直接安装新版本（升级安装）

下载新版本安装包直接双击安装即可，安装程序会自动：

1. 检测已安装的旧版本（安装向导会明确提示"将自动升级到 vX.Y.Z"）
2. 跳过安装目录选择页，原地升级，不产生第二份安装
3. 让正在运行的应用主动退出（旧版本则会等待几秒后强制结束）
4. 升级完成后自动重新启动应用
5. 工作数据、报告、待办和设置完整保留

> 无需先卸载旧版本，直接装新版本即可。

### 应用内自动更新（无需任何配置）

「设置 → 关于与更新」里可以：

- 点「检查更新」：从本项目的 GitHub Releases 获取最新版本，有新版本时提示，一键下载、静默安装并自动重启
- 点「选择安装包升级」：手动选择一个新版安装包，程序退出后自动升级并重启
- 「启动时自动检查更新」默认开启；检查失败（断网、无法访问等）会静默跳过，不弹错误

**内置更新源**（普通用户不需要填写任何地址）：

```
https://github.com/MINMIN-CN/Worklog/releases/latest/download/manifest.json
```

> 网络请求使用系统证书库，兼容安装了 HTTPS 根证书（企业代理、安全软件）的环境。

如需自定义（例如自建镜像、内网分发），在数据目录 `config.json` 中修改：

```json
{ "update": { "manifest_url": "https://你的地址/manifest.json", "auto_check": true } }
```

更新清单（manifest）格式：

```json
{
  "version": "0.4.0",
  "url": "https://你的地址/WorkLog-Setup-0.4.0.exe",
  "notes": "更新说明，可省略"
}
```

### 发布新版本（开发者）

1. 改版本号后运行 `packaging\build.bat` 生成安装包
2. 更新 `update/manifest.json`（version、url、notes）
3. 用 GitHub CLI 发布 Release，把安装包和 manifest 作为资源上传：

```bat
gh release create v0.5.0 "dist\installer\WorkLog-Setup-0.5.0.exe" "update\manifest.json" ^
  --title "工作小记 v0.5.0" --notes "更新说明"
```

4. 应用会自动通过 `releases/latest/download/manifest.json` 发现新版本。

## 数据与备份

不同运行方式的数据位置：

| 运行方式 | 数据目录 |
| --- | --- |
| 源码运行（run.bat） | 项目下的 `data/` |
| 安装版 | 程序安装目录下的 `data/`（默认 `%LOCALAPPDATA%\Programs\工作小记\data`） |
| 安装版（程序目录不可写时） | 自动回退到 `%LOCALAPPDATA%\WorkLog\data` |
| 便携版 | 程序目录的 `data/`（在 exe 旁新建 `portable.txt` 即启用） |

**旧版本数据迁移**：升级安装后首次启动时，如果检测到旧版本在 `%LOCALAPPDATA%\WorkLog\data` 下的数据，
会自动复制到程序目录并校验，原目录改名为 `data_已迁移_可删除` 作为备份，确认无误后可手动删除。

**卸载**：卸载时会明确询问「删除数据 / 保留数据」：

- **保留数据**：先把 `data` 移动到 `%LOCALAPPDATA%\WorkLog\data`，再删除程序；以后重装会自动迁移回来
- **删除数据**：连同工作记录、报告、待办和 AI 配置一起删除

```
data/
├── config.json      # 配置（含 API Key，注意不要外发）
├── worklog.db       # 所有记录、报告、待办
├── reports/         # 生成报告的 Markdown 副本
└── tmp/             # 临时目录（正常情况下为空）
```

- 备份：直接复制整个 `data/` 目录。
- 导出：设置页「导出全部数据」可导出 JSON。
- 清理：设置页「清空所有记录」。
- 崩溃排查：安装版如果启动失败，会写日志到数据目录下的 `worklog_error.log`。

## 开发者信息

```bat
uv run python tools/smoke_test.py      :: 核心模块 + 界面构造冒烟测试
uv run python tools/flow_test.py       :: mock 模型接口的全链路测试
uv run python tools/app_start_test.py  :: 应用启动退出测试
```

目录结构：

```
worklog/
├── app.py             # 入口
├── config.py          # 配置与路径
├── db.py              # SQLite 数据层
├── capture.py         # 截屏、压缩、去重指纹
├── wininfo.py         # 前台窗口 / 空闲 / 锁屏检测
├── ai.py              # OpenAI 兼容客户端
├── providers.py       # 热门服务商预设
├── analyze.py         # 视觉分析、文本分类、待办提取
├── stats.py           # 统计计算
├── reporting.py       # 报告模板与生成
├── recorder.py        # 采集线程 + 分析线程
├── agent_api.py       # 本地 HTTP API
└── ui/                # 界面（PySide6）
```

## 打包成安装包

先安装一次 Inno Setup（只需一次）：

```bat
winget install JRSoftware.InnoSetup
```

然后运行：

```bat
packaging\build.bat
```

它会依次：生成图标 → PyInstaller 打包（onedir，输出 `dist\WorkLog\`）→ Inno Setup 生成安装包。

产物：`dist\installer\WorkLog-Setup-0.5.0.exe`，安装包特性：

- 默认按用户安装（无需管理员权限），路径 `%LOCALAPPDATA%\Programs\工作小记`
- 安装向导支持**简体中文 / English**，自动匹配系统语言
- 可选创建桌面快捷方式、开机自启动
- 数据默认存放在安装目录下的 `data\`
- 支持**原地升级**：检测旧版本、跳过目录页、自动关闭并重启应用、数据完整保留
- 卸载时明确询问「删除数据 / 保留数据」；选保留会自动把数据移到 `%LOCALAPPDATA%\WorkLog\data`，重装后自动迁回
- 升级安装时若发现旧版数据（`%LOCALAPPDATA%\WorkLog\data`）会自动迁移

> 首次运行安装包时，火绒/Windows Defender 可能对 PyInstaller 打包的程序弹窗询问，选择允许即可。

# 更新日志

本文件记录公开版本的主要变化，格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。
每个版本的完整发布说明见 [Releases](https://github.com/MINMIN-CN/Worklog/releases)。

## [0.5.3] - 2026-10-07

### 新增

- 设置页新增「开机自动启动」开关：安装版可在应用内随时开启/关闭，登录后静默进入托盘后台记录
- 新增 `--minimized` 启动参数（开机自启用，不弹出主窗口）

### 修复

- 英文模式设置页 DeepSeek 服务商说明残留中文的问题
- 卸载时清理开机自启动注册表项和旧版启动文件夹快捷方式

## [0.5.2] - 2026-10-02

### 修复

- 修复 DeepSeek「思考模式」占满输出预算，导致生成的日报/周报内容为空、列表点开看不到内容的问题
- 模型输出被长度截断时自动翻倍输出预算重试；仍为空则明确报错，不再保存空报告

### 新增

- 高级设置新增「思考模式」「思考强度」，DeepSeek 预设默认关闭思考模式
- AI 客户端支持 `thinking` / `reasoning_effort` 参数

### 变更

- 报告生成的输出预算从 2000 提升到 3000

## [0.5.1] - 2026-10-02

### 新增

- 应用内更新支持国内加速：自动测速并选择最快的 GitHub 镜像线路
- 多连接分段下载，线路故障自动切换
- 下载进度条、实时速度显示与取消按钮

## [0.5.0] - 2026-10-02

### 新增

- 完整简体中文 / English 双语界面，可在设置中切换（重启生效）
- 安装向导自动匹配系统语言
- 新增英文说明 [README.en.md](README.en.md)

## [0.4.2] - 2026-10-02

### 修复

- 修复中文安装路径下自动更新重启失败的问题

## [0.4.1] - 2026-10-02

### 修复

- 兼容本机 HTTPS 拦截环境：HTTPS 校验改用 Windows 系统证书库

## [0.4.0] - 2026-10-02

### 新增

- 内置自动更新源，用户无需手动填写任何更新地址
- 发布 `manifest.json` 更新清单，应用自动发现新版本

## [0.3.0] - 2026-10-02

### 新增

- 首个公开版本：自动截屏记录与 AI 分析、时间线、统计、日报/周报/月报、待办、本地 Agent API、系统托盘

[0.5.3]: https://github.com/MINMIN-CN/Worklog/releases/tag/v0.5.3
[0.5.2]: https://github.com/MINMIN-CN/Worklog/releases/tag/v0.5.2
[0.5.1]: https://github.com/MINMIN-CN/Worklog/releases/tag/v0.5.1
[0.5.0]: https://github.com/MINMIN-CN/Worklog/releases/tag/v0.5.0
[0.4.2]: https://github.com/MINMIN-CN/Worklog/releases/tag/v0.4.2
[0.4.1]: https://github.com/MINMIN-CN/Worklog/releases/tag/v0.4.1
[0.4.0]: https://github.com/MINMIN-CN/Worklog/releases/tag/v0.4.0
[0.3.0]: https://github.com/MINMIN-CN/Worklog/releases/tag/v0.3.0

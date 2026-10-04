# 安全政策

**简体中文** | [English](#english)

## 支持的版本

只有**最新发布版本**会收到安全修复。反馈问题前，请先通过应用内「设置 → 关于与更新」升级到最新版。

## 报告漏洞

请**不要**通过公开 Issue 报告安全漏洞。请使用 GitHub 的私密报告通道：

1. 打开本仓库的 **Security** 标签页
2. 点击 **Report a vulnerability**
3. 说明问题描述、复现步骤和影响范围

如果无法使用该通道，也可以先开一个 Issue，仅说明「需要私下沟通」，维护者会回复其他联系方式。

## 本应用的安全设计

- 截图只在内存中用于一次 AI 分析，**分析完立即销毁，不写入磁盘**
- 工作记录、报告、待办保存在本机数据目录（默认安装目录的 `data\`）
- API Key 保存在本机 `config.json`，只会发送给你自己配置的模型服务商
- 本地 Agent API 默认只监听 `127.0.0.1`，局域网内其他设备无法访问
- 更新从 GitHub Releases 或其镜像下载，升级前校验版本号与文件名

## 请勿公开的内容

在 Issue / PR 中请勿包含：API Key、真实工作记录截图或内容、以及他人的隐私数据。

## English

### Supported versions

Only the **latest release** receives security fixes. Please update to the latest version (Settings → About & Updates) before reporting.

### Reporting a vulnerability

Please **do not** report security vulnerabilities through public issues. Use GitHub's private reporting instead:

1. Open the **Security** tab of this repository
2. Click **Report a vulnerability**
3. Describe the issue, steps to reproduce, and impact

If that channel is unavailable, open an issue stating only that a private conversation is needed.

### Security design notes

- Screenshots are used in memory for a single AI analysis and destroyed immediately — nothing is written to disk.
- Records, reports and todos are stored locally (default: `data\` inside the install directory).
- The API key is stored in the local `config.json` and is only sent to the provider you configure.
- The local Agent API listens on `127.0.0.1` only.
- Updates are downloaded from GitHub Releases (or its mirrors); version and file name are verified before install.

### What not to share

Never include API keys, real work-record screenshots/content, or other people's private data in issues or PRs.

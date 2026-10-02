# WorkLog (工作小记)
[简体中文](README.md) | **English**

A local-first AI work journal and daily-report assistant for Windows desktop. Independently built, using the core workflow of Bilibili's "小黑日报助手" (Xiaohei Daily Report Assistant) as a reference:

> Auto-track your work → AI understands the content → generate daily / weekly / monthly reports → extract to-dos → connect your own Agent

Screenshots live only in memory for a single AI analysis and **are destroyed immediately afterwards — nothing is written to disk**; work records, reports, and to-dos are all stored locally in the `data/` directory.

## Feature overview

| Module | Description |
| --- | --- |
| Auto capture | Takes screenshots at a set interval and records the foreground app and window title at the same time; frames that haven't changed are merged automatically, so no AI calls are wasted |
| AI understanding | A multimodal model reads the content and auto-classifies it (development / meetings / communication / documents …), generating summaries, projects, and tags; privacy-masking prompts are built in |
| Timeline | Browse work records by day; edit, delete, add manual entries, and run text-only re-analysis on records that haven't been analyzed |
| Statistics | Focus time, app usage ranking, category breakdown, week × hour heatmap, and frequent tags |
| Reports | One-click daily / weekly / monthly reports with 4 built-in report templates and support for extra instructions; finished reports are saved to the database and exported as Markdown |
| To-dos | Add them manually, or let AI extract them from a day's timeline; supports due dates and completion status |
| Local Agent API | HTTP endpoints on 127.0.0.1 that read the timeline / stats / reports and also write records and to-dos |
| System tray | Closing the window minimizes it to the tray and recording continues; pause / resume / capture now at any time |
| UI language | Simplified Chinese / English; follows the system by default and can be switched in settings (takes effect after restart); the installer wizard also matches the system language automatically |

## Quick start

With `uv` installed, run the following in this directory:

```bat
install.bat     :: install dependencies (first time only; skip if you've done this before)
run.bat         :: launch the app (no console window)
run_debug.bat   :: for troubleshooting, with console logs
```

Or do it manually:

```bat
uv sync
uv run python -m worklog
```

After the first launch, open "Settings" on the left, fill in your AI endpoint, and save. Recording works fine without an API key (only app names and window titles are captured); once it's configured, you can click "Re-analyze unanalyzed" on historical records.

## Configuring the AI endpoint (foolproof)

Open "Settings → AI Model Endpoint" and complete three steps:

1. Pick a **provider** from the dropdown (built-in presets for DeepSeek, Qwen, Zhipu GLM, SiliconFlow, Kimi, Volcano Ark, Tencent Hunyuan, Baidu Qianfan, OpenAI, and local Ollama)
2. Paste that provider's **API Key**
3. Click "**Test connection**" (it checks the text model and the vision model separately); when it passes, click "Save settings"

Once a provider is selected, the endpoint URL and model name are filled in automatically and usually need no changes. To use a custom endpoint or model name, expand "**Advanced settings**" and edit them manually. On first launch you'll also see a "Go to settings" prompt button on the "Today" page.

> 💡 **DeepSeek already supports image input natively** (`deepseek-flash`, since 2026-09), and it's this tool's default preset: direct access from mainland China, low cost, no proxy required.
> 💡 Model names may change as providers update. If the test says "model not found", switch to the provider's latest model name under advanced settings.

Configuration is saved to `config.json` in the data directory and can also be edited directly.

## Usage tips

- **Capture interval**: 120 seconds by default. Too short burns more AI quota; too long loses detail. If you're worried about quota, start with 300 seconds.
- **Excluded apps**: Password managers like KeePass and 1Password are excluded by default. Add sensitive apps such as WeChat or your personal email as needed (one process name per line, e.g. `WeChat.exe`).
- **Idle pause**: Recording stops after 5 minutes without keyboard or mouse activity by default and resumes automatically when you're back; it also pauses while the screen is locked.
- **Merge rules**: When the window and app stay the same and the screen looks similar, the time is added to the previous record (`×N` = number of captures); AI is only called when the screen changes noticeably.
- **Launch at startup**: Check "Start with Windows" in the installer, or put a shortcut to `run.bat` in the `shell:startup` folder.

## Local Agent API

Listens on `http://127.0.0.1:8765` by default (the port can be changed or the API disabled in settings).

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/health` | Health check |
| GET | `/api/timeline?date=YYYY-MM-DD` or `?start=&end=` | Work timeline |
| GET | `/api/stats?date=` or `?start=&end=` | Aggregated statistics |
| GET | `/api/app-usage?date=` | App usage time |
| GET | `/api/todos` | To-do list |
| GET | `/api/reports`, `/api/reports/{id}` | Report list / details |
| POST | `/api/records` | Write a work record (JSON: `title`, `app`, `start_ts`…) |
| POST | `/api/todos` | Create a to-do |
| PATCH | `/api/todos/{id}` | Update to-do status with `{"status": "done"}` |

Example:

```bat
curl "http://127.0.0.1:8765/api/timeline?date=2026-10-02"
```

That way your own Agent (OpenCode, Cherry Studio, etc.) can read your work data directly, or write completed items back to the timeline.

## Privacy

- Screenshots are captured with `mss`, compressed and encoded in memory only, then sent to the model endpoint you configured; they are released immediately after analysis and never written to disk.
- Before anything is sent to the model, the prompt requires privacy masking: no names, accounts, passwords, or raw chat text are recorded, and private screens are marked simply as "private content".
- All structured records, reports, and to-dos are stored locally in `data/worklog.db` (SQLite).
- Screens matching the exclusion list are never captured.
- The local API binds only to `127.0.0.1` and is unreachable from the LAN.

## Upgrade and auto update

### Installing a new version directly (upgrade install)

Download the new installer and double-click it to install; the setup automatically:

1. Detects the previously installed version (the wizard clearly shows "will automatically upgrade to vX.Y.Z")
2. Skips the install-directory page and performs an in-place upgrade, so no second installation is created
3. Asks the running app to exit gracefully (older versions are waited on for a few seconds and then force-closed)
4. Restarts the app automatically when the upgrade is complete
5. Keeps all work data, reports, to-dos, and settings intact

> No need to uninstall the old version first — just install the new one.

### Built-in auto update (no configuration needed)

Under "Settings → About & Updates" you can:

- Click "Check for updates": fetch the latest version from this project's GitHub Releases; if a newer version exists you'll be prompted, and one click downloads, installs silently, and restarts automatically
- Click "Upgrade from installer": manually select a new installer; after the app exits it upgrades and restarts automatically
- "Check for updates at startup" is enabled by default; if the check fails (offline, unreachable, etc.) it is skipped silently with no error dialog

**Built-in update source** (regular users don't need to enter any URL):

```
https://github.com/MINMIN-CN/Worklog/releases/latest/download/manifest.json
```

> Network requests use the system certificate store, so it works in environments with an HTTPS root certificate installed (corporate proxies, security software).

To customize it (for example a self-hosted mirror or intranet distribution), edit `config.json` in the data directory:

```json
{ "update": { "manifest_url": "https://your-host/manifest.json", "auto_check": true } }
```

Update manifest format:

```json
{
  "version": "0.4.0",
  "url": "https://your-host/WorkLog-Setup-0.4.0.exe",
  "notes": "Release notes, optional"
}
```

### Publishing a new version (developers)

1. Bump the version number, then run `packaging\build.bat` to build the installer
2. Update `update/manifest.json` (version, url, notes)
3. Publish a Release with the GitHub CLI, uploading the installer and manifest as assets:

```bat
gh release create v0.5.0 "dist\installer\WorkLog-Setup-0.5.0.exe" "update\manifest.json" ^
  --title "WorkLog v0.5.0" --notes "Release notes"
```

4. The app will automatically discover the new version via `releases/latest/download/manifest.json`.

## Data and backups

Data locations by run mode:

| Run mode | Data directory |
| --- | --- |
| Running from source (run.bat) | `data/` under the project |
| Installed version | `data/` under the install directory (default `%LOCALAPPDATA%\Programs\工作小记\data`) |
| Installed version (when the program directory is not writable) | Falls back to `%LOCALAPPDATA%\WorkLog\data` |
| Portable version | `data/` in the program directory (create a `portable.txt` next to the exe to enable) |

**Data migration from older versions**: On the first launch after an upgrade install, if data from an older version is found under `%LOCALAPPDATA%\WorkLog\data`, it is copied to the program directory and verified; the original directory is renamed to `data_已迁移_可删除` as a backup, which you can delete manually once you've confirmed everything is in order.

**Uninstall**: The uninstaller explicitly asks whether to "Delete data / Keep data":

- **Keep data**: `data` is first moved to `%LOCALAPPDATA%\WorkLog\data`, then the program is removed; reinstalling later migrates it back automatically
- **Delete data**: work records, reports, to-dos, and the AI configuration are all deleted

```
data/
├── config.json      # Configuration (includes the API Key; do not share)
├── worklog.db       # All records, reports, and to-dos
├── reports/         # Markdown copies of generated reports
└── tmp/             # Temporary directory (normally empty)
```

- Backup: just copy the entire `data/` directory.
- Export: "Export all data" on the settings page exports JSON.
- Cleanup: "Clear all records" on the settings page.
- Crash troubleshooting: if the installed version fails to start, it writes a log to `worklog_error.log` in the data directory.

## Developer information

```bat
uv run python tools/smoke_test.py      :: core modules + UI construction smoke test
uv run python tools/flow_test.py       :: full-flow test with a mock model endpoint
uv run python tools/app_start_test.py  :: app start and exit test
```

Directory structure:

```
worklog/
├── app.py             # Entry point
├── config.py          # Configuration and paths
├── db.py              # SQLite data layer
├── capture.py         # Screenshot capture, compression, dedup fingerprints
├── wininfo.py         # Foreground window / idle / lock screen detection
├── ai.py              # OpenAI-compatible client
├── providers.py       # Popular provider presets
├── analyze.py         # Vision analysis, text classification, to-do extraction
├── stats.py           # Statistics computation
├── reporting.py       # Report templates and generation
├── recorder.py        # Capture thread + analysis thread
├── agent_api.py       # Local HTTP API
└── ui/                # UI (PySide6)
```

## Packaging the installer

Install Inno Setup once:

```bat
winget install JRSoftware.InnoSetup
```

Then run:

```bat
packaging\build.bat
```

It runs in sequence: generate icons → PyInstaller packaging (onedir, output to `dist\WorkLog\`) → Inno Setup to build the installer.

Output: `dist\installer\WorkLog-Setup-0.5.0.exe`. Installer features:

- Per-user install by default (no administrator rights required), at `%LOCALAPPDATA%\Programs\工作小记`
- The installer wizard supports **Simplified Chinese / English** and matches the system language automatically
- Optionally creates a desktop shortcut and enables launch at startup
- Data is stored in `data\` under the install directory by default
- Supports **in-place upgrades**: detects the old version, skips the directory page, closes and restarts the app automatically, and keeps all data intact
- On uninstall it explicitly asks "Delete data / Keep data"; if you choose to keep it, the data is moved automatically to `%LOCALAPPDATA%\WorkLog\data` and migrated back after reinstall
- During an upgrade install, data from an older version (`%LOCALAPPDATA%\WorkLog\data`) is migrated automatically

> The first time you run the installer, Huorong/Windows Defender may prompt about the PyInstaller-packaged program; just choose Allow.

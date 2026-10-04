"""主窗口：侧边导航 + 页面堆栈 + 系统托盘。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, i18n
from ..config import DATA_DIR
from ..updater import (
    download_installer,
    fetch_manifest,
    is_newer,
    launch_update,
    resolve_manifest_url,
)
from .pages import (
    ReportsPage,
    SettingsPage,
    StatsPage,
    TimelinePage,
    TodayPage,
    TodosPage,
)
from .widgets import ProgressTask, Task, make_icon, refresh_style

STATUS_LABELS = {
    "recording": "记录中",
    "paused": "已暂停",
    "idle": "离开中",
    "analyzing": "AI 分析中",
    "stopped": "已停止",
}


class MainWindow(QMainWindow):
    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._really_quit = False
        self._tray_notified = False

        self.setWindowTitle(i18n.tr("工作小记 · 工作记录与日报助手"))
        self.resize(1240, 820)
        self.setWindowIcon(make_icon())

        root = QWidget()
        root.setObjectName("root")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(150)
        for name in ["今日", "时间线", "统计", "报告", "待办", "设置"]:
            self.nav.addItem(i18n.tr(name))
        root_layout.addWidget(self.nav)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        topbar = QWidget()
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(18, 12, 18, 6)
        topbar_layout.setSpacing(8)

        self.pill = QLabel("已停止")
        self.pill.setObjectName("pill")
        self.pill.setProperty("state", "stopped")
        self.message_label = QLabel("")
        self.message_label.setObjectName("muted")
        self.capture_btn = QPushButton("立即记录")
        self.capture_btn.setObjectName("ghost")
        self.capture_btn.clicked.connect(ctx.engine.capture_now)
        self.pause_btn = QPushButton("暂停记录")
        self.pause_btn.setObjectName("primary")
        self.pause_btn.clicked.connect(ctx.engine.toggle_pause)

        topbar_layout.addWidget(self.pill)
        topbar_layout.addWidget(self.message_label)
        topbar_layout.addStretch(1)
        topbar_layout.addWidget(self.capture_btn)
        topbar_layout.addWidget(self.pause_btn)
        right.addWidget(topbar)

        self.stack = QStackedWidget()
        self.today_page = TodayPage(ctx)
        self.timeline_page = TimelinePage(ctx)
        self.stats_page = StatsPage(ctx)
        self.reports_page = ReportsPage(ctx)
        self.todos_page = TodosPage(ctx)
        self.settings_page = SettingsPage(ctx)
        for page in (
            self.today_page,
            self.timeline_page,
            self.stats_page,
            self.reports_page,
            self.todos_page,
            self.settings_page,
        ):
            self.stack.addWidget(page)
        right.addWidget(self.stack, 1)

        root_layout.addLayout(right, 1)
        self.setCentralWidget(root)

        self.nav.currentRowChanged.connect(self._on_nav_changed)
        self.nav.setCurrentRow(0)

        self.today_page.open_reports.connect(self._open_reports)
        self.today_page.open_settings.connect(lambda: self.nav.setCurrentRow(5))
        self.today_page.data_changed.connect(self._refresh_all)
        self.timeline_page.data_changed.connect(self._refresh_all)
        self.todos_page.data_changed.connect(self._refresh_all)

        self._setup_tray()

        ctx.engine.status_changed.connect(self._on_status)
        ctx.engine.record_added.connect(self._on_record_changed)
        ctx.engine.record_updated.connect(self._on_record_changed)
        ctx.engine.error.connect(self._show_message)

        self._timer = QTimer(self)
        self._timer.setInterval(60000)
        self._timer.timeout.connect(self._refresh_current)
        self._timer.start()

        # 安装程序升级前会写入 .installer_close 标记，应用看到后主动退出以便替换文件
        self._installer_timer = QTimer(self)
        self._installer_timer.setInterval(2000)
        self._installer_timer.timeout.connect(self._check_installer_close)
        self._installer_timer.start()

        if ctx.engine.running:
            self._on_status("paused" if ctx.engine.paused else "recording")
        else:
            self._on_status("stopped")

        QTimer.singleShot(4000, self._auto_check_update)
        i18n.translate_widget_tree(self)

    # ------------------------------------------------------------------ 更新
    def _check_installer_close(self) -> None:
        import time

        marker = DATA_DIR / ".installer_close"
        if not marker.exists():
            return
        try:
            fresh = time.time() - marker.stat().st_mtime < 600
        except Exception:
            fresh = False
        if not fresh:
            return
        try:
            marker.unlink()
        except Exception:
            pass
        self._really_quit = True
        self.close()

    def _auto_check_update(self) -> None:
        enabled = bool(self.ctx.cfg.get("update", "auto_check", default=True))
        if not enabled:
            return
        source = resolve_manifest_url(self.ctx.cfg)
        task = Task(lambda: fetch_manifest(source), self)
        task.done.connect(self._on_manifest_checked)
        # 启动时检查失败（断网、无法访问等）静默忽略，不打扰用户
        task.fail.connect(lambda _message: None)
        self._update_task = task
        task.start()

    def _on_manifest_checked(self, manifest: dict) -> None:
        remote = str(manifest.get("version") or "")
        if not is_newer(remote):
            return
        notes = str(manifest.get("notes") or "").strip()
        message = i18n.tr("发现新版本 v{remote}（当前 v{current}）").format(
            remote=remote, current=__version__
        )
        if notes:
            message += f"\n\n{notes}"
        message += "\n\n" + i18n.tr("是否立即下载并自动安装？安装完成后程序会自动重新打开。")
        if QMessageBox.question(self, i18n.tr("检查更新"), message) != QMessageBox.Yes:
            return
        url = str(manifest.get("url") or "")
        if not url:
            self._show_message(i18n.tr("更新清单缺少下载地址 url"))
            return
        mirrors = manifest.get("mirror_prefixes") or manifest.get("mirrors") or []
        self._download_dialog = QProgressDialog(
            i18n.tr("正在测试下载线路…"), i18n.tr("取消"), 0, 100, self
        )
        self._download_dialog.setWindowTitle(i18n.tr("更新"))
        self._download_dialog.setWindowModality(Qt.WindowModal)
        self._download_dialog.setMinimumDuration(0)
        self._download_dialog.setValue(0)
        self._download_dialog.canceled.connect(self._cancel_download)
        task = ProgressTask(
            lambda report, cancel: download_installer(
                url,
                progress=report,
                cancel=cancel,
                extra_mirrors=list(mirrors),
                cfg=self.ctx.cfg,
            ),
            self,
        )
        task.progress.connect(self._on_download_progress)
        task.done.connect(self._install_downloaded)
        task.fail.connect(self._on_download_failed)
        task.cancelled.connect(self._on_download_cancelled)
        self._update_task = task
        task.start()

    def _cancel_download(self) -> None:
        task = getattr(self, "_update_task", None)
        if isinstance(task, ProgressTask):
            task.cancel()

    def _close_download_dialog(self) -> None:
        dialog = getattr(self, "_download_dialog", None)
        if dialog is not None:
            dialog.close()
            self._download_dialog = None

    def _on_download_progress(
        self, done: int, total: int, speed: float, source: str
    ) -> None:
        dialog = getattr(self, "_download_dialog", None)
        if dialog is None:
            return
        if total <= 0:
            dialog.setLabelText(i18n.tr("正在测试下载线路…"))
            return
        dialog.setValue(min(100, int(done * 100 / total)))
        mb = 1024 * 1024
        speed_text = (
            f"{speed / mb:.2f} MB" if speed >= mb else f"{speed / 1024:.0f} KB"
        )
        dialog.setLabelText(
            i18n.tr("正在下载 {done}/{total} MB · {speed}/s · {source}").format(
                done=f"{done / mb:.1f}",
                total=f"{total / mb:.1f}",
                speed=speed_text,
                source=source or "—",
            )
        )

    def _on_download_cancelled(self) -> None:
        self._close_download_dialog()
        self._show_message(i18n.tr("已取消下载"))

    def _on_download_failed(self, message: str) -> None:
        self._close_download_dialog()
        self._show_message(i18n.tr("下载失败：{message}").format(message=message))

    def _install_downloaded(self, path) -> None:
        self._close_download_dialog()
        try:
            launch_update(path)
        except Exception as exc:
            self._show_message(i18n.tr("更新启动失败：{message}").format(message=exc))
            return
        QApplication.quit()

    # ------------------------------------------------------------------ 导航
    def _on_nav_changed(self, row: int) -> None:
        self.stack.setCurrentIndex(row)
        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()

    def _open_reports(self, kind: str) -> None:
        self.reports_page.prefill(kind)
        self.nav.setCurrentRow(3)

    def _refresh_current(self) -> None:
        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()

    def _refresh_all(self) -> None:
        self.today_page.refresh()
        self.timeline_page.refresh()
        self.stats_page.refresh()

    # ------------------------------------------------------------------ 引擎
    def _on_status(self, status: str) -> None:
        base = (status or "stopped").split(":", 1)[0]
        label = STATUS_LABELS.get(base, "异常")
        self.pill.setText(i18n.tr(label))
        self.pill.setProperty("state", base if base in STATUS_LABELS else "error")
        refresh_style(self.pill)
        paused = base == "paused"
        pause_text = i18n.tr("继续记录" if paused else "暂停记录")
        self.pause_btn.setText(pause_text)
        self.tray_pause_action.setText(pause_text)

    def _on_record_changed(self, _payload: dict) -> None:
        page = self.stack.currentWidget()
        if page in (self.today_page, self.timeline_page, self.stats_page):
            page.refresh()

    def _show_message(self, text: str) -> None:
        self.message_label.setText(text)
        QTimer.singleShot(8000, lambda: self.message_label.setText(""))

    # ------------------------------------------------------------------ 托盘
    def _setup_tray(self) -> None:
        self.tray = QSystemTrayIcon(make_icon(), self)
        self.tray.setToolTip(i18n.tr("工作小记 · 工作记录与日报助手"))
        menu = QMenu()
        show_action = menu.addAction("显示主窗口")
        show_action.triggered.connect(self._show_window)
        self.tray_pause_action = menu.addAction("暂停记录")
        self.tray_pause_action.triggered.connect(self.ctx.engine.toggle_pause)
        capture_action = menu.addAction("立即记录")
        capture_action.triggered.connect(self.ctx.engine.capture_now)
        menu.addSeparator()
        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(self._quit)
        self.tray_menu = menu
        i18n.translate_menu(menu)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.isVisible():
                self.hide()
            else:
                self._show_window()

    def _show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit(self) -> None:
        self._really_quit = True
        self.close()

    # ------------------------------------------------------------------ 关闭
    def closeEvent(self, event) -> None:
        close_to_tray = self.ctx.cfg.get("ui", "close_to_tray", default=True)
        if not self._really_quit and close_to_tray and self.tray.isVisible():
            event.ignore()
            self.hide()
            if not self._tray_notified:
                self.tray.showMessage(
                    i18n.tr("工作小记"),
                    i18n.tr("已最小化到托盘，记录继续运行。"),
                    QSystemTrayIcon.Information,
                    3000,
                )
                self._tray_notified = True
            return
        self.ctx.engine.stop()
        if self.ctx.api:
            self.ctx.api.stop()
        event.accept()
        QApplication.quit()

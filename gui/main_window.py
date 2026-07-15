"""Main desktop window and background scan worker."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QThread, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QCloseEvent, QDesktopServices
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QSplitter, QStatusBar, QTextEdit, QVBoxLayout, QWidget,
)

from analyzer.project_scan import ProjectScanner, ScanCancelled, ScanResult
from report import write_reports
from .result_widget import ResultWidget
from .upload_widget import UploadWidget


class ScanWorker(QObject):
    progress = pyqtSignal(int, int, str)
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, source: str, language: str) -> None:
        super().__init__()
        self.source = source
        self.language = language
        self.scanner = ProjectScanner()

    @pyqtSlot()
    def run(self) -> None:
        try:
            result = self.scanner.scan(self.source, self.language, self.progress.emit)
            output_directory = Path(__file__).resolve().parents[1] / "output"
            write_reports(result, output_directory)
        except ScanCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        else:
            self.completed.emit(result)
        finally:
            self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ProjectQuickStar - 企业项目智能分析工具")
        self.resize(1180, 760)
        self._thread: QThread | None = None
        self._worker: ScanWorker | None = None

        self.upload_widget = UploadWidget()
        self.result_widget = ResultWidget()
        splitter = QSplitter()
        splitter.addWidget(self.upload_widget)
        splitter.addWidget(self.result_widget)
        splitter.setSizes([390, 790])

        self.start_button = QPushButton("开始分析")
        self.pause_button = QPushButton("暂停")
        self.cancel_button = QPushButton("取消任务")
        self.markdown_button = QPushButton("打开 Markdown 报告")
        self.html_button = QPushButton("打开 HTML 报告")
        self.pause_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.markdown_button.setEnabled(False)
        self.html_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_scan)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.cancel_button.clicked.connect(self.cancel_scan)
        self.markdown_button.clicked.connect(lambda: self._open_report("markdown"))
        self.html_button.clicked.connect(lambda: self._open_report("html"))

        button_row = QHBoxLayout()
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.pause_button)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.markdown_button)
        button_row.addWidget(self.html_button)
        button_row.addStretch(1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_label = QLabel("等待开始")
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(115)

        central = QWidget()
        layout = QVBoxLayout(central)
        title = QLabel("企业项目智能分析工具")
        title.setStyleSheet("font-size: 22px; font-weight: 600; padding: 8px 0;")
        layout.addWidget(title)
        layout.addWidget(splitter, 1)
        layout.addLayout(button_row)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("第一阶段：项目上传、目录扫描与语言检测")

    @pyqtSlot()
    def start_scan(self) -> None:
        source = self.upload_widget.source_path
        if not source:
            QMessageBox.warning(self, "缺少项目", "请先选择项目目录或压缩包。")
            return
        if not Path(source).exists():
            QMessageBox.warning(self, "路径无效", f"项目路径不存在：\n{source}")
            return

        self.result_widget.clear_result()
        self.progress_bar.setValue(0)
        self.progress_label.setText("正在准备扫描……")
        self.log.clear()
        self.markdown_button.setEnabled(False)
        self.html_button.setEnabled(False)
        self._set_running(True)

        thread = QThread(self)
        worker = ScanWorker(source, self.upload_widget.selected_language)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.cancelled.connect(self._on_cancelled)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._release_worker)
        self._thread = thread
        self._worker = worker
        thread.start()

    @pyqtSlot()
    def toggle_pause(self) -> None:
        if self._worker is None:
            return
        if self._worker.scanner.is_paused:
            self._worker.scanner.resume()
            self.pause_button.setText("暂停")
            self.progress_label.setText("继续扫描……")
            self.log.append("任务已继续")
        else:
            self._worker.scanner.pause()
            self.pause_button.setText("继续")
            self.progress_label.setText("任务已暂停")
            self.log.append("任务已暂停")

    @pyqtSlot()
    def cancel_scan(self) -> None:
        if self._worker is not None:
            self._worker.scanner.cancel()
            self.cancel_button.setEnabled(False)
            self.progress_label.setText("正在取消……")
            self.log.append("已请求取消任务")

    @pyqtSlot(int, int, str)
    def _on_progress(self, current: int, total: int, message: str) -> None:
        percent = int(current * 100 / total) if total else 100
        self.progress_bar.setValue(percent)
        self.progress_label.setText(f"{message}（{current:,}/{total:,}）")

    @pyqtSlot(object)
    def _on_completed(self, result: ScanResult) -> None:
        self.result_widget.show_result(result)
        self.progress_bar.setValue(100)
        self.progress_label.setText("分析完成")
        self.log.append(f"扫描完成：{result.total_files:,} 个文件，跳过 {result.skipped_files:,} 个文件")
        self._report_paths = result.report_paths
        self.markdown_button.setEnabled("markdown" in result.report_paths)
        self.html_button.setEnabled("html" in result.report_paths)
        if result.report_paths:
            self.log.append(f"Markdown 报告：{result.report_paths.get('markdown', '')}")
            self.log.append(f"HTML 报告：{result.report_paths.get('html', '')}")
        for warning in result.warnings[:10]:
            self.log.append(f"警告：{warning}")
        self._set_running(False)

    @pyqtSlot(str)
    def _on_failed(self, message: str) -> None:
        self.progress_label.setText("分析失败")
        self.log.append(message)
        self._set_running(False)
        QMessageBox.critical(self, "分析失败", message)

    @pyqtSlot()
    def _on_cancelled(self) -> None:
        self.progress_label.setText("任务已取消")
        self.log.append("任务已安全取消")
        self._set_running(False)

    @pyqtSlot()
    def _release_worker(self) -> None:
        self._thread = None
        self._worker = None

    def _set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.upload_widget.setEnabled(not running)
        self.pause_button.setEnabled(running)
        self.cancel_button.setEnabled(running)
        if not running:
            self.pause_button.setText("暂停")

    def _open_report(self, report_type: str) -> None:
        path = getattr(self, "_report_paths", {}).get(report_type)
        if path and Path(path).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            QMessageBox.warning(self, "报告不存在", "请先完成一次项目分析。")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._thread is not None and self._thread.isRunning():
            answer = QMessageBox.question(self, "任务运行中", "分析任务仍在运行，确定取消并退出吗？")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            if self._worker is not None:
                self._worker.scanner.cancel()
            self._thread.quit()
            self._thread.wait(3000)
        event.accept()

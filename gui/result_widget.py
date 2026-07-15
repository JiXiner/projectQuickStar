"""Scan summary and project tree presentation."""

from __future__ import annotations

from PyQt6.QtWidgets import QHeaderView, QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from analyzer.project_scan import ScanResult


class ResultWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.summary = QLabel("尚未运行分析")
        self.summary.setWordWrap(True)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["项目结构", "类型", "大小"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)
        layout.addWidget(self.tree, 1)

    def clear_result(self) -> None:
        self.summary.setText("正在分析……")
        self.tree.clear()

    def show_result(self, result: ScanResult) -> None:
        languages = "、".join(f"{name} {count}" for name, count in result.detected_languages.items()) or "未检测到支持的源码"
        self.summary.setText(
            f"项目：{result.project_name}　文件：{result.total_files:,}　"
            f"大小：{self._human_size(result.total_bytes)}　耗时：{result.duration_seconds:.3f} 秒\n"
            f"语言分布：{languages}"
        )
        self.tree.clear()
        root_item = QTreeWidgetItem([result.project_name, "目录", ""])
        self.tree.addTopLevelItem(root_item)
        directory_items = {"": root_item}
        for record in result.files:
            parts = record.path.split("/")
            parent_key = ""
            parent_item = root_item
            for directory in parts[:-1]:
                key = f"{parent_key}/{directory}" if parent_key else directory
                if key not in directory_items:
                    directory_items[key] = QTreeWidgetItem([directory, "目录", ""])
                    parent_item.addChild(directory_items[key])
                parent_item = directory_items[key]
                parent_key = key
            parent_item.addChild(
                QTreeWidgetItem([parts[-1], record.extension or "文件", self._human_size(record.size)])
            )
        root_item.setExpanded(True)

    @staticmethod
    def _human_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if value < 1024 or unit == "TB":
                return f"{value:.1f} {unit}"
            value /= 1024
        return f"{value:.1f} TB"

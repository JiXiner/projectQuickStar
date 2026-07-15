"""Input controls for selecting a project and analysis scope."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)


class UploadWidget(QWidget):
    source_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("选择本地项目目录或项目压缩包")
        self.path_edit.textChanged.connect(self.source_changed)

        directory_button = QPushButton("选择目录")
        directory_button.clicked.connect(self._choose_directory)
        archive_button = QPushButton("上传压缩包")
        archive_button.clicked.connect(self._choose_archive)

        source_row = QHBoxLayout()
        source_row.addWidget(self.path_edit, 1)
        source_row.addWidget(directory_button)
        source_row.addWidget(archive_button)

        self.language_combo = QComboBox()
        self.language_combo.addItems(["自动检测", "Python", "Java", "PHP", "Go", "JavaScript"])

        language_form = QFormLayout()
        language_form.addRow("项目语言：", self.language_combo)
        language_group = QGroupBox("语言选择")
        language_group.setLayout(language_form)

        analysis_group = QGroupBox("分析内容")
        analysis_layout = QVBoxLayout()
        self.structure_check = QCheckBox("项目结构分析")
        self.structure_check.setChecked(True)
        self.structure_check.setEnabled(False)
        analysis_layout.addWidget(self.structure_check)
        self.code_check = QCheckBox("代码功能分析与报告生成")
        self.code_check.setChecked(True)
        self.code_check.setEnabled(False)
        analysis_layout.addWidget(self.code_check)
        for label in ("数据库分析", "Redis 分析", "MQ 分析", "服务调用分析", "AI 智能解释"):
            checkbox = QCheckBox(label)
            checkbox.setEnabled(False)
            analysis_layout.addWidget(checkbox)
        analysis_group.setLayout(analysis_layout)

        layout = QVBoxLayout(self)
        layout.addLayout(source_row)
        layout.addWidget(language_group)
        layout.addWidget(analysis_group)
        layout.addStretch(1)

    @property
    def source_path(self) -> str:
        return self.path_edit.text().strip()

    @property
    def selected_language(self) -> str:
        return self.language_combo.currentText()

    def _choose_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择项目目录")
        if path:
            self.path_edit.setText(str(Path(path)))

    def _choose_archive(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择项目压缩包",
            "",
            "项目压缩包 (*.zip *.rar *.tar *.tar.gz *.tgz)",
        )
        if path:
            self.path_edit.setText(str(Path(path)))

"""
DataSelectorWidget — 通用数据集选择控件
========================================
任何插件的面板中都可以直接使用，提供：
  - 下拉框：列出 DataManager 中已加载的数据集（可按 dtype 过滤）
  - 路径输入框：手动填写或由下拉框自动填入
  - 浏览按钮：打开文件选择对话框

用法示例（在插件 _build_panel 中）：
    from ui.data_selector import DataSelectorWidget

    sel = DataSelectorWidget(
        data_manager = ctx.data,          # DataManager | None
        dtypes       = ["GeoTIFF"],       # 仅显示 GeoTIFF 类型（省略则显示全部）
        file_filter  = "GeoTIFF (*.tif *.tiff);;所有文件 (*)",
        placeholder  = "选择 GeoTIFF 文件...",
    )
    form.addRow("输入文件:", sel)
    path = sel.get_path()                 # 读取当前路径
"""

from __future__ import annotations

import os
from typing import Optional, List

from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)


class DataSelectorWidget(QWidget):
    """下拉框 + 路径输入 + 浏览按钮的组合控件，可感知 DataManager 变化。"""

    path_changed = pyqtSignal(str)   # 路径改变时发射

    def __init__(
        self,
        data_manager=None,           # DataManager | None
        dtypes: Optional[List[str]] = None,
        file_filter: str = "所有文件 (*)",
        placeholder: str = "选择文件或从上方下拉框选择",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._dm       = data_manager
        self._dtypes   = dtypes or []
        self._filter   = file_filter

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        # ── 下拉框 ──────────────────────────────────────────────────────────
        self._combo = QComboBox()
        self._combo.setObjectName("_combo")
        lay.addWidget(self._combo)

        # ── 路径行 ──────────────────────────────────────────────────────────
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText(placeholder)
        self._edit.setObjectName("_edit")
        self._edit.textChanged.connect(self.path_changed)

        btn = QPushButton("浏览")
        btn.setFixedWidth(55)
        btn.setProperty("secondary", True)
        btn.clicked.connect(self._browse)

        rl.addWidget(self._edit)
        rl.addWidget(btn)
        lay.addWidget(row)

        # ── 初始填充 & 信号连接 ──────────────────────────────────────────────
        self._rebuild_combo()
        self._combo.currentIndexChanged.connect(self._on_combo_changed)

        if self._dm is not None:
            self._dm.dataset_added.connect(self._on_dm_changed)
            self._dm.dataset_removed.connect(self._on_dm_changed)
            self._dm.cleared.connect(self._on_dm_cleared)

    # ── 公开接口 ─────────────────────────────────────────────────────────────

    def get_path(self) -> str:
        """返回当前选择/输入的文件路径（已 strip）。"""
        return self._edit.text().strip()

    def set_path(self, path: str):
        """以代码方式设置路径（同时尝试在下拉框中匹配）。"""
        self._edit.setText(path)
        idx = self._combo.findData(path)
        if idx >= 0:
            self._combo.blockSignals(True)
            self._combo.setCurrentIndex(idx)
            self._combo.blockSignals(False)

    # ── 内部 ─────────────────────────────────────────────────────────────────

    def _rebuild_combo(self):
        prev_path = self._combo.currentData()

        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItem("— 从数据面板选择 —", None)

        if self._dm is not None:
            entries = (
                self._dm.by_type(*self._dtypes)
                if self._dtypes
                else self._dm.all()
            )
            for e in entries:
                self._combo.addItem(f"{e.icon} {e.name}  [{e.dtype}]", e.path)

        # 恢复之前的选择
        if prev_path:
            idx = self._combo.findData(prev_path)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)

        self._combo.blockSignals(False)

    def _on_combo_changed(self, _idx: int):
        path = self._combo.currentData()
        if path:
            self._edit.setText(path)

    def _on_dm_changed(self, _ds_id: str = ""):
        self._rebuild_combo()

    def _on_dm_cleared(self):
        self._rebuild_combo()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文件",
            os.path.dirname(self._edit.text()) or "",
            self._filter,
        )
        if path:
            self._edit.setText(path)
            # 尝试在下拉框中高亮匹配
            idx = self._combo.findData(path)
            if idx >= 0:
                self._combo.blockSignals(True)
                self._combo.setCurrentIndex(idx)
                self._combo.blockSignals(False)

"""
算法库插件
==========
一个插件管理所有反演算法：
  - 顶部下拉菜单选择算法
  - 中部参数区根据所选算法动态生成控件
  - 底部运行按钮 + 进度条
  - 结果统一叠加到地图 / 写入日志

新增算法只需：
  1. 在 algorithms/ 目录下新建 .py 文件，继承 AlgorithmBase
  2. 在 algorithms/__init__.py 的 REGISTRY 中注册
"""

import os
import sys

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QProgressBar, QPushButton, QScrollArea,
    QSpinBox, QVBoxLayout, QWidget,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from plugins.base import BasePlugin
from ui.data_selector import DataSelectorWidget


# ─────────────────────────────────────────────────────────────────────────────
#  后台执行线程（驱动算法生成器）
# ─────────────────────────────────────────────────────────────────────────────

class _AlgoRunner(QThread):
    progress     = pyqtSignal(int, str)
    result_ready = pyqtSignal(dict)
    failed       = pyqtSignal(str)

    def __init__(self, algo, params):
        super().__init__()
        self._algo   = algo
        self._params = params

    def run(self):
        try:
            for item in self._algo.run(self._params):
                if isinstance(item, tuple) and item[0] == "done":
                    self.result_ready.emit(item[1])
                elif isinstance(item, tuple) and len(item) == 2:
                    pct, msg = item
                    self.progress.emit(int(pct), str(msg))
        except Exception:
            import traceback
            self.failed.emit(traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
#  插件主类
# ─────────────────────────────────────────────────────────────────────────────

class Plugin(BasePlugin):
    LAYER_ID = "algo_library_result"

    def on_load(self, ctx):
        self.ctx    = ctx
        self._panel = None
        self._worker = None
        self._algos  = []      # [AlgorithmBase实例, ...]
        self._cur_algo = None
        self._param_widgets = {}   # key → QWidget
        self._load_algorithms()
        ctx.log(f"[算法库] 已加载 {len(self._algos)} 个算法")

    def _load_algorithms(self):
        try:
            sys.path.insert(0, os.path.dirname(__file__))
            from algorithms import REGISTRY
            self._algos = [cls() for cls in REGISTRY]
        except Exception as e:
            self.ctx.log(f"[算法库] 算法加载失败: {e}")

    def on_unload(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()
        self.ctx.map.remove_layer(self.LAYER_ID)

    def get_panel(self):
        if not self._panel:
            self._panel = self._build_panel()
        return self._panel

    def get_viz_tabs(self):
        return []

    # ── UI 构建 ─────────────────────────────────────────────────────────────

    def _build_panel(self):
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        title = QLabel("算法库")
        title.setProperty("title", True)
        lay.addWidget(title)

        # 算法选择
        grp_sel = QGroupBox("选择算法")
        f_sel = QFormLayout(grp_sel)
        self._algo_combo = QComboBox()
        for algo in self._algos:
            self._algo_combo.addItem(algo.name)
        self._algo_combo.currentIndexChanged.connect(self._on_algo_changed)
        f_sel.addRow("算法:", self._algo_combo)

        self._algo_desc = QLabel("")
        self._algo_desc.setWordWrap(True)
        self._algo_desc.setProperty("subtitle", True)
        f_sel.addRow(self._algo_desc)
        lay.addWidget(grp_sel)

        # 动态参数区（可滚动）
        self._param_group = QGroupBox("算法参数")
        self._param_form  = QFormLayout(self._param_group)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._param_group)
        scroll.setMaximumHeight(260)
        lay.addWidget(scroll)

        # 进度
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        lay.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setProperty("subtitle", True)
        self._status.setWordWrap(True)
        lay.addWidget(self._status)

        # 按钮
        self._run_btn = QPushButton("运行算法")
        self._run_btn.clicked.connect(self._run)
        lay.addWidget(self._run_btn)

        btn_clear = QPushButton("清除图层")
        btn_clear.setProperty("secondary", True)
        btn_clear.clicked.connect(lambda: self.ctx.map.remove_layer(self.LAYER_ID))
        lay.addWidget(btn_clear)

        lay.addStretch()

        # 初始化第一个算法
        if self._algos:
            self._on_algo_changed(0)

        return root

    def _on_algo_changed(self, idx: int):
        if idx < 0 or idx >= len(self._algos):
            return
        algo = self._algos[idx]
        self._cur_algo = algo
        self._algo_desc.setText(algo.description)

        # 清空旧控件
        while self._param_form.rowCount() > 0:
            self._param_form.removeRow(0)
        self._param_widgets.clear()

        # 根据 schema 生成新控件
        for spec in algo.param_schema:
            widget = self._make_widget(spec)
            if widget:
                key = spec["key"]
                self._param_widgets[key] = widget
                self._param_form.addRow(spec["label"] + ":", widget)

    def _make_widget(self, spec: dict) -> QWidget:
        t = spec.get("type", "str")

        if t == "file":
            # 使用通用 DataSelectorWidget，自动感知 DataManager 变化
            dm = getattr(self.ctx, "data", None)
            return DataSelectorWidget(
                data_manager=dm,
                dtypes=spec.get("dtypes", []),
                file_filter=spec.get("filter", "所有文件 (*)"),
                placeholder=spec.get("default", "选择文件或从上方下拉框选择"),
            )

        if t == "file_save":
            # 输出路径：若有工程则默认填入工作目录
            container = QWidget()
            row = QHBoxLayout(container)
            row.setContentsMargins(0, 0, 0, 0)
            edit = QLineEdit()
            edit.setPlaceholderText(spec.get("default", "留空则不保存"))
            edit.setObjectName("_edit")
            btn = QPushButton("浏览")
            btn.setFixedWidth(55)
            btn.setProperty("secondary", True)
            flt = spec.get("filter", "所有文件 (*)")
            btn.clicked.connect(lambda _, e=edit, f=flt: self._browse_file_save(e, f))
            row.addWidget(edit)
            row.addWidget(btn)
            return container

        if t == "float":
            w = QDoubleSpinBox()
            w.setRange(spec.get("min", -1e9), spec.get("max", 1e9))
            w.setSingleStep(spec.get("step", 0.1))
            w.setDecimals(4)
            w.setValue(float(spec.get("default", 0)))
            return w

        if t == "int":
            w = QSpinBox()
            w.setRange(int(spec.get("min", -99999)), int(spec.get("max", 99999)))
            w.setValue(int(spec.get("default", 0)))
            return w

        if t == "bool":
            w = QCheckBox()
            w.setChecked(bool(spec.get("default", False)))
            return w

        if t == "choice":
            w = QComboBox()
            choices = spec.get("choices", [])
            w.addItems(choices)
            default = spec.get("default", "")
            if default in choices:
                w.setCurrentText(default)
            return w

        # 默认文本框
        w = QLineEdit()
        w.setText(str(spec.get("default", "")))
        return w

    def _browse_file_save(self, edit, flt: str):
        """file_save 类型专用：保存对话框。"""
        path, _ = QFileDialog.getSaveFileName(self._panel, "保存结果", "", flt)
        if path:
            edit.setText(path)

    # ── 运行逻辑 ─────────────────────────────────────────────────────────────

    def _collect_params(self) -> dict:
        """从动态控件中收集当前参数值。"""
        params = {}
        for key, widget in self._param_widgets.items():
            if isinstance(widget, DataSelectorWidget):
                # file 类型：DataSelectorWidget 直接提供 get_path()
                params[key] = widget.get_path()
            elif hasattr(widget, "_dm_edit"):
                # file_save 类型：旧式容器，内部有 _dm_edit（QLineEdit）
                params[key] = widget._dm_edit.text().strip()
            elif isinstance(widget, QDoubleSpinBox):
                params[key] = widget.value()
            elif isinstance(widget, QSpinBox):
                params[key] = widget.value()
            elif isinstance(widget, QCheckBox):
                params[key] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                params[key] = widget.currentText()
            elif isinstance(widget, QLineEdit):
                params[key] = widget.text().strip()
        return params

    def _run(self):
        if not self._cur_algo:
            self.ctx.log("[算法库] 未选择算法")
            return
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()

        params = self._collect_params()

        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._status.setText("正在运行...")

        self._worker = _AlgoRunner(self._cur_algo, params)
        self._worker.progress.connect(self._on_progress)
        self._worker.result_ready.connect(lambda r: self._on_done(r, params))
        self._worker.failed.connect(self._on_fail)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_progress(self, pct: int, msg: str):
        self._progress.setValue(pct)
        self._status.setText(msg)
        self.ctx.events.publish("progress", pct)

    def _on_done(self, result: dict, params: dict):
        self._run_btn.setEnabled(True)
        self._progress.setVisible(False)
        self.ctx.events.publish("progress", -1)

        data   = result.get("data")
        bounds = result.get("bounds", (-90, -180, 90, 180))

        if data is not None:
            try:
                from ui.map_widget import array_to_data_url
                cmap = params.get("colormap", "viridis")
                data_url = array_to_data_url(data, cmap)
                self.ctx.map.add_image_overlay(
                    self.LAYER_ID, data_url,
                    bounds[0], bounds[1], bounds[2], bounds[3],
                    opacity=0.8,
                )
            except Exception as e:
                self.ctx.log(f"[算法库] 地图叠加失败: {e}")

        for k, v in result.get("stats", {}).items():
            val = f"{v:.4f}" if isinstance(v, float) else str(v)
            self.ctx.log(f"  {k}: {val}")

        msg = result.get("message", "算法完成")
        self._status.setText(msg)
        self.ctx.log(f"[算法库·{self._cur_algo.name}] {msg}")

    def _on_fail(self, tb: str):
        self._run_btn.setEnabled(True)
        self._progress.setVisible(False)
        self.ctx.events.publish("progress", -1)
        self._status.setText("算法失败")
        self.ctx.log(f"[算法库] 失败:\n{tb}")

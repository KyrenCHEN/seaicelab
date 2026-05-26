"""
冰间水道提取演示插件 (2D)
演示如何在平台中集成 GeoTIFF 输入 → 算法处理 → 2D 地图可视化的完整流程。
"""

import os
import sys

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
    QLabel, QProgressBar, QPushButton,
    QSlider, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from plugins.base import BasePlugin
from ui.data_selector import DataSelectorWidget


class IceChannelWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, params):
        super().__init__()
        self.params = params

    def run(self):
        try:
            self.progress.emit(10, "读取数据...")
            data = self._load(self.params["input"])

            self.progress.emit(40, "水道初步提取...")
            mask = self._extract_channel(data, self.params["threshold"])

            self.progress.emit(70, "形态学后处理...")
            mask = self._morphology(mask, self.params["morph_iter"])

            self.progress.emit(90, "生成结果...")
            self.progress.emit(100, "完成")
            self.finished.emit({"mask": mask, "raw": data})
        except Exception as e:
            self.failed.emit(str(e))

    def _load(self, path: str) -> np.ndarray:
        try:
            import rasterio
            with rasterio.open(path) as src:
                return src.read(1).astype(np.float32)
        except ImportError:
            from PIL import Image
            return np.array(Image.open(path)).astype(np.float32)

    def _extract_channel(self, data: np.ndarray, threshold: float) -> np.ndarray:
        valid = data[data != 0]
        if len(valid) == 0:
            return np.zeros_like(data, dtype=np.uint8)
        lo, hi = np.percentile(valid, 2), np.percentile(valid, 98)
        norm = (data - lo) / (hi - lo + 1e-8)
        return (norm < threshold).astype(np.uint8)

    def _morphology(self, mask: np.ndarray, iterations: int) -> np.ndarray:
        from scipy.ndimage import binary_opening, binary_closing
        result = binary_opening(mask, iterations=iterations)
        result = binary_closing(result, iterations=iterations)
        return result.astype(np.uint8)


class Plugin(BasePlugin):
    LAYER_RAW = "ice_channel_raw"
    LAYER_MASK = "ice_channel_mask"

    def on_load(self, ctx):
        self.ctx = ctx
        self._worker = None
        self._panel = None
        ctx.log(f"[{self.name}] 已加载")

    def on_unload(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()
        for lid in (self.LAYER_RAW, self.LAYER_MASK):
            self.ctx.map.remove_layer(lid)
        self.ctx.log(f"[{self.name}] 已卸载")

    def get_panel(self) -> QWidget:
        if self._panel:
            return self._panel
        self._panel = self._build_panel()
        return self._panel

    def _build_panel(self) -> QWidget:
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        title = QLabel("冰间水道提取")
        title.setProperty("title", True)
        lay.addWidget(title)

        desc = QLabel("基于亮温/后向散射阈值分割，提取冰间水道掩膜")
        desc.setProperty("subtitle", True)
        desc.setWordWrap(True)
        lay.addWidget(desc)

        grp_in = QGroupBox("输入数据")
        form = QFormLayout(grp_in)
        self._data_sel = DataSelectorWidget(
            data_manager=self.ctx.data,
            dtypes=["GeoTIFF"],
            file_filter="GeoTIFF (*.tif *.tiff);;所有文件 (*)",
            placeholder="GeoTIFF 文件路径...",
        )
        form.addRow("输入:", self._data_sel)
        lay.addWidget(grp_in)

        grp_param = QGroupBox("算法参数")
        pform = QFormLayout(grp_param)

        self._thresh = QDoubleSpinBox()
        self._thresh.setRange(0.01, 0.99)
        self._thresh.setSingleStep(0.05)
        self._thresh.setValue(0.25)
        self._thresh.setDecimals(2)
        pform.addRow("水道阈值:", self._thresh)

        self._morph = QDoubleSpinBox()
        self._morph.setRange(1, 10)
        self._morph.setValue(2)
        self._morph.setDecimals(0)
        pform.addRow("形态学迭代次数:", self._morph)

        self._show_raw = QComboBox()
        self._show_raw.addItems(["仅显示掩膜", "仅显示原始数据", "两者叠加"])
        pform.addRow("显示模式:", self._show_raw)

        lay.addWidget(grp_param)

        grp_layer = QGroupBox("图层透明度")
        lform = QFormLayout(grp_layer)
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(10, 100)
        self._opacity_slider.setValue(80)
        self._opacity_slider.valueChanged.connect(
            lambda v: self.ctx.map.set_layer_opacity(self.LAYER_MASK, v / 100)
        )
        lform.addRow("透明度:", self._opacity_slider)
        lay.addWidget(grp_layer)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        lay.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setProperty("subtitle", True)
        lay.addWidget(self._status)

        self._run_btn = QPushButton("开始提取")
        self._run_btn.clicked.connect(self._run)
        lay.addWidget(self._run_btn)

        btn_clear = QPushButton("清除图层")
        btn_clear.setProperty("secondary", True)
        btn_clear.clicked.connect(self._clear)
        lay.addWidget(btn_clear)

        lay.addStretch()
        return root

    def _run(self):
        path = self._data_sel.get_path()
        if not path or not os.path.exists(path):
            self.ctx.log("[冰间水道] 请选择有效的输入文件")
            return

        params = {
            "input": path,
            "threshold": self._thresh.value(),
            "morph_iter": int(self._morph.value()),
        }

        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._worker = IceChannelWorker(params)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_done)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _on_progress(self, pct, msg):
        self._progress.setValue(pct)
        self._status.setText(msg)

    def _on_done(self, result):
        self._run_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._status.setText("提取完成")

        from ui.map_widget import _array_to_data_url
        mode = self._show_raw.currentIndex()
        opacity = self._opacity_slider.value() / 100

        if mode in (1, 2):
            url = _array_to_data_url(result["raw"], "gray")
            self.ctx.map.add_image_overlay(self.LAYER_RAW, url, -90, -180, 90, 180, 0.6)
        if mode in (0, 2):
            mask_float = result["mask"].astype(np.float32)
            url = _array_to_data_url(mask_float, "Blues")
            self.ctx.map.add_image_overlay(self.LAYER_MASK, url, -90, -180, 90, 180, opacity)

        self.ctx.log(f"[冰间水道] 提取完成，水道像素占比: "
                     f"{result['mask'].mean() * 100:.2f}%")

    def _on_fail(self, msg):
        self._run_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._status.setText(f"失败: {msg}")
        self.ctx.log(f"[冰间水道] 失败: {msg}")

    def _clear(self):
        self.ctx.map.remove_layer(self.LAYER_RAW)
        self.ctx.map.remove_layer(self.LAYER_MASK)
        self._status.setText("")

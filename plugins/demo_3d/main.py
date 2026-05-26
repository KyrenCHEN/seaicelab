"""
三维地物可视化演示插件 (3D)
多波段 GeoTIFF → 选择 Z 波段 → Z 坐标变换 → 交互式三维曲面渲染。

Z 坐标变换说明
  - 原始:    直接使用像素值，可能非常平坦
  - 归一化:  映射到 [0, 1]，适合量纲差异大的场景
  - 对数:    log1p 压缩动态范围，适合厚尾分布
  - 平方根:  sqrt 轻度压缩
垂直拉伸（Z Scale）在变换之后叠加应用，可夸大地形起伏。
"""

import os
import sys

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton,
    QSizePolicy, QSpinBox, QToolButton, QVBoxLayout, QWidget,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from plugins.base import BasePlugin
from ui.data_selector import DataSelectorWidget

try:
    import matplotlib
    matplotlib.rcParams['font.sans-serif'] = [
        'Arial Unicode MS', 'PingFang SC', 'Heiti TC', 'SimHei', 'DejaVu Sans'
    ]
    matplotlib.rcParams['axes.unicode_minus'] = False
    matplotlib.use("QtAgg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


# ─────────────────────────────────────────────────────────────────────────────
#  工具栏（图标染白，适配深色背景）
# ─────────────────────────────────────────────────────────────────────────────

def _tint_icon(icon: "QIcon", color: QColor) -> "QIcon":
    """将 QIcon 的不透明像素全部染为指定颜色（保留 alpha 形状）。"""
    new_icon = QIcon()
    sizes = icon.availableSizes()
    if not sizes:
        sizes = [icon.actualSize(icon.availableSizes()[0]) if icon.availableSizes() else None]
        sizes = [s for s in sizes if s is not None]
    for size in sizes:
        src = icon.pixmap(size)
        result = QPixmap(src.size())
        result.fill(Qt.GlobalColor.transparent)
        p = QPainter(result)
        p.drawPixmap(0, 0, src)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(result.rect(), color)
        p.end()
        new_icon.addPixmap(result)
    return new_icon


if HAS_MPL:
    class _WhiteNavToolbar(NavigationToolbar2QT):
        """NavigationToolbar2QT 子类：图标统一染为白色以适配深色主题。"""
        _ICON_COLOR = QColor("#D0E8F8")   # 淡冰蓝白

        def __init__(self, canvas, parent):
            super().__init__(canvas, parent)
            self._recolor_all_icons()

        def _recolor_all_icons(self):
            for btn in self.findChildren(QToolButton):
                icon = btn.icon()
                if not icon.isNull():
                    btn.setIcon(_tint_icon(icon, self._ICON_COLOR))
else:
    _WhiteNavToolbar = None   # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
#  后台加载 / 计算线程
# ─────────────────────────────────────────────────────────────────────────────

class Surface3DWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    def __init__(self, params: dict):
        super().__init__()
        self.params = params

    def run(self):
        try:
            self.progress.emit(10, "读取文件...")
            data, bounds, band_names, nodata = self._load(self.params["path"])

            self.progress.emit(35, "提取 Z 波段...")
            z_idx = self.params["z_band_idx"]
            z_raw = data[z_idx].astype(np.float32)
            if nodata is not None:
                z_raw[z_raw == nodata] = np.nan

            self.progress.emit(55, "降采样...")
            max_pts = self.params["max_pts"]
            h, w = z_raw.shape
            sy = max(1, h // max_pts)
            sx = max(1, w // max_pts)
            z_ds = z_raw[::sy, ::sx]

            self.progress.emit(70, "Z 坐标变换...")
            z_tr = self._transform(z_ds, self.params["z_transform"])

            # 垂直拉伸
            z_scale = float(self.params["z_scale"])
            if self.params["z_auto_scale"]:
                # 让 Z 范围约等于 XY 的 15%
                z_span = float(np.nanmax(z_tr) - np.nanmin(z_tr))
                xy_span = max(z_tr.shape)
                z_scale = (xy_span * 0.15 / z_span) if z_span > 1e-9 else 1.0
            z_final = z_tr * z_scale

            # 建立 XY 网格（归一化到 [0,1]）
            rows, cols = z_final.shape
            x = np.linspace(0, 1, cols)
            y = np.linspace(0, 1, rows)
            X, Y = np.meshgrid(x, y)

            z_raw_range = (float(np.nanmin(z_ds)), float(np.nanmax(z_ds)))
            z_tr_range  = (float(np.nanmin(z_tr)), float(np.nanmax(z_tr)))

            self.progress.emit(95, "准备渲染数据...")
            self.finished.emit({
                "X": X, "Y": Y, "Z": z_final,
                "z_raw_range": z_raw_range,
                "z_tr_range":  z_tr_range,
                "z_scale":     z_scale,
                "band_names":  band_names,
                "z_band_name": band_names[z_idx] if z_idx < len(band_names) else f"波段{z_idx+1}",
                "bounds":      bounds,
                "z_transform": self.params["z_transform"],
            })
            self.progress.emit(100, "完成")
        except Exception as e:
            import traceback
            self.failed.emit(traceback.format_exc())

    # ── 辅助 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _load(path: str):
        try:
            import rasterio
            with rasterio.open(path) as src:
                raw = src.read().astype(np.float32)
                nodata = src.nodata
                bounds = (src.bounds.left, src.bounds.bottom,
                          src.bounds.right, src.bounds.top)
                descs = src.descriptions or []
                band_names = [
                    (descs[i] if i < len(descs) and descs[i] else f"波段 {i+1}")
                    for i in range(src.count)
                ]
                return raw, bounds, band_names, nodata
        except ImportError:
            from PIL import Image
            img = Image.open(path)
            arr = np.array(img).astype(np.float32)
            if arr.ndim == 2:
                arr = arr[np.newaxis]
            else:
                arr = arr.transpose(2, 0, 1)
            names = [f"波段 {i+1}" for i in range(arr.shape[0])]
            return arr, None, names, None

    @staticmethod
    def _transform(z: np.ndarray, mode: str) -> np.ndarray:
        if mode == "归一化 [0,1]":
            lo, hi = np.nanmin(z), np.nanmax(z)
            if hi > lo:
                return (z - lo) / (hi - lo)
            return np.zeros_like(z)
        elif mode == "对数 log(1+x)":
            shifted = z - np.nanmin(z)
            return np.log1p(np.maximum(shifted, 0))
        elif mode == "平方根":
            shifted = z - np.nanmin(z)
            return np.sqrt(np.maximum(shifted, 0))
        else:  # 原始
            return z.copy()


# ─────────────────────────────────────────────────────────────────────────────
#  三维曲面画布（中央 Tab）
# ─────────────────────────────────────────────────────────────────────────────

class Surface3DCanvas(QWidget):
    BG = "#080F1A"
    PANE = "#0D1826"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cbar = None   # 当前 colorbar 引用，用于下次渲染前移除

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        if not HAS_MPL:
            lay.addWidget(QLabel("需安装 matplotlib 和 mpl_toolkits"))
            return

        self._fig = plt.figure(figsize=(8, 6))
        self._fig.patch.set_facecolor(self.BG)
        self._ax3d = self._fig.add_subplot(111, projection="3d")
        self._style_axes()

        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        toolbar = _WhiteNavToolbar(self._canvas, self)
        toolbar.setStyleSheet(
            "background:#0D1826; border:none; border-bottom:1px solid #1A3050;"
            "QToolButton{ color:#D0E8F8; background:transparent; padding:4px; border:none; }"
            "QToolButton:hover{ background:rgba(0,196,232,0.12); }"
            "QToolButton:checked{ background:rgba(0,196,232,0.20); }"
        )
        lay.addWidget(toolbar)
        lay.addWidget(self._canvas, stretch=1)

        # 信息标签
        self._info = QLabel("")
        self._info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info.setStyleSheet(
            "color:#3A6080; font-size:11px; background:#080F1A; padding:4px;"
        )
        lay.addWidget(self._info)

    def _style_axes(self):
        ax = self._ax3d
        ax.set_facecolor(self.PANE)
        for pane in (ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane):
            pane.set_facecolor(self.PANE)
            pane.set_edgecolor("#1A3050")
        ax.tick_params(colors="#3A6080", labelsize=8)
        ax.xaxis.label.set_color("#3A6080")
        ax.yaxis.label.set_color("#3A6080")
        ax.zaxis.label.set_color("#3A6080")
        ax.grid(True, alpha=0.12)

    def render(self, data: dict, colormap: str):
        if not HAS_MPL:
            return

        # 必须先移除旧 colorbar，再 clear 坐标轴；
        # 顺序反了 colorbar.remove() 会因 subplot spec 为 None 而崩溃
        if self._cbar is not None:
            try:
                self._cbar.remove()
            except Exception:
                pass
            self._cbar = None

        self._ax3d.clear()
        self._style_axes()

        X, Y, Z = data["X"], data["Y"], data["Z"]
        Z_plot = np.ma.array(Z, mask=np.isnan(Z))

        surf = self._ax3d.plot_surface(
            X, Y, Z_plot,
            cmap=colormap,
            alpha=0.92,
            linewidth=0,
            antialiased=True,
            rcount=100, ccount=100,
        )

        z_name  = data.get("z_band_name", "Z")
        z_tr    = data.get("z_transform", "")
        z_scale = data.get("z_scale", 1.0)
        lo_raw, hi_raw = data.get("z_raw_range", (0, 1))

        self._ax3d.set_xlabel("X (归一化)", fontsize=9, color="#4A7090", labelpad=8)
        self._ax3d.set_ylabel("Y (归一化)", fontsize=9, color="#4A7090", labelpad=8)
        self._ax3d.set_zlabel(
            f"Z ({z_name}{'  '+z_tr if z_tr != '原始' else ''})",
            fontsize=9, color="#4A7090", labelpad=8
        )

        self._cbar = self._fig.colorbar(surf, ax=self._ax3d, shrink=0.45, aspect=12,
                                        pad=0.1, label=z_name)
        self._fig.tight_layout(pad=0.5)
        self._canvas.draw()

        tr_lbl = z_tr if z_tr != "原始" else "未变换"
        self._info.setText(
            f"波段: {z_name}   变换: {tr_lbl}   "
            f"原始范围: [{lo_raw:.3g}, {hi_raw:.3g}]   垂直拉伸: ×{z_scale:.2f}"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  插件本体
# ─────────────────────────────────────────────────────────────────────────────

class Plugin(BasePlugin):

    def on_load(self, ctx):
        self.ctx = ctx
        self._panel  = None
        self._canvas = None
        self._worker = None
        self._band_names: list[str] = []
        ctx.log(f"[{self.name}] 已加载")

    def on_unload(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()
        self.ctx.log(f"[{self.name}] 已卸载")

    def get_panel(self) -> QWidget:
        if not self._panel:
            self._panel = self._build_panel()
        return self._panel

    def get_viz_tabs(self) -> list:
        if not self._canvas:
            self._canvas = Surface3DCanvas()
        return [("三维视图", self._canvas)]

    # ── 面板构建 ──────────────────────────────────────────────────────────

    def _build_panel(self) -> QWidget:
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        title = QLabel("三维地物可视化")
        title.setProperty("title", True)
        lay.addWidget(title)

        desc = QLabel("多波段 GeoTIFF → 选波段作 Z 轴 → 三维曲面")
        desc.setProperty("subtitle", True)
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # 输入文件
        grp_in = QGroupBox("输入数据")
        f_in = QFormLayout(grp_in)

        self._data_sel = DataSelectorWidget(
            data_manager=self.ctx.data,
            dtypes=["GeoTIFF"],
            file_filter="GeoTIFF (*.tif *.tiff);;所有文件 (*)",
            placeholder="多波段 GeoTIFF 文件...",
        )
        self._data_sel.path_changed.connect(self._on_path_changed)
        f_in.addRow("文件:", self._data_sel)

        self._band_info = QLabel("—")
        self._band_info.setProperty("subtitle", True)
        f_in.addRow("波段数:", self._band_info)
        lay.addWidget(grp_in)

        # Z 轴设置
        grp_z = QGroupBox("Z 轴配置")
        f_z = QFormLayout(grp_z)

        self._z_band_combo = QComboBox()
        self._z_band_combo.setPlaceholderText("请先选择文件")
        f_z.addRow("Z 波段:", self._z_band_combo)

        self._z_transform = QComboBox()
        self._z_transform.addItems(["原始", "归一化 [0,1]", "对数 log(1+x)", "平方根"])
        self._z_transform.setCurrentIndex(1)  # 默认归一化
        f_z.addRow("Z 变换:", self._z_transform)

        self._auto_scale = QComboBox()
        self._auto_scale.addItems(["自动拉伸（推荐）", "手动指定"])
        self._auto_scale.currentIndexChanged.connect(self._on_scale_mode)
        f_z.addRow("垂直拉伸:", self._auto_scale)

        self._z_scale_spin = QDoubleSpinBox()
        self._z_scale_spin.setRange(0.001, 10000)
        self._z_scale_spin.setValue(1.0)
        self._z_scale_spin.setDecimals(3)
        self._z_scale_spin.setEnabled(False)
        f_z.addRow("拉伸系数:", self._z_scale_spin)
        lay.addWidget(grp_z)

        # 渲染设置
        grp_r = QGroupBox("渲染设置")
        f_r = QFormLayout(grp_r)

        self._colormap = QComboBox()
        self._colormap.addItems([
            "viridis", "plasma", "inferno", "magma",
            "coolwarm", "RdYlBu_r", "ocean", "terrain",
            "YlOrRd", "Blues",
        ])
        f_r.addRow("色彩映射:", self._colormap)

        self._max_pts = QSpinBox()
        self._max_pts.setRange(50, 600)
        self._max_pts.setValue(200)
        self._max_pts.setSuffix(" px")
        f_r.addRow("最大分辨率:", self._max_pts)
        lay.addWidget(grp_r)

        # 进度 & 状态
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        lay.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setProperty("subtitle", True)
        self._status.setWordWrap(True)
        lay.addWidget(self._status)

        self._render_btn = QPushButton("开始渲染")
        self._render_btn.clicked.connect(self._run)
        lay.addWidget(self._render_btn)

        lay.addStretch()
        return root

    def _on_scale_mode(self, idx: int):
        self._z_scale_spin.setEnabled(idx == 1)

    # ── 逻辑 ──────────────────────────────────────────────────────────────

    def _on_path_changed(self, path: str):
        """路径变化时自动刷新波段信息。"""
        if path and os.path.exists(path):
            self._load_band_info(path)

    def _load_band_info(self, path: str):
        self._z_band_combo.clear()
        self._band_names = []
        try:
            try:
                import rasterio
                with rasterio.open(path) as src:
                    n = src.count
                    descs = src.descriptions or []
                    self._band_names = [
                        (descs[i] if i < len(descs) and descs[i] else f"波段 {i+1}")
                        for i in range(n)
                    ]
            except ImportError:
                from PIL import Image
                img = Image.open(path)
                arr = np.array(img)
                n = 1 if arr.ndim == 2 else arr.shape[2]
                self._band_names = [f"波段 {i+1}" for i in range(n)]
            self._band_info.setText(str(len(self._band_names)))
            self._z_band_combo.addItems(self._band_names)
            # 默认选最后一个波段作为 Z（通常是高程/厚度等）
            self._z_band_combo.setCurrentIndex(len(self._band_names) - 1)
            self.ctx.log(f"[3D] 文件包含 {len(self._band_names)} 个波段")
        except Exception as e:
            self.ctx.log(f"[3D] 读取波段信息失败: {e}")

    def _run(self):
        path = self._data_sel.get_path()
        if not path or not os.path.exists(path):
            self.ctx.log("[3D] 请先选择有效的文件")
            return
        if not self._band_names:
            self.ctx.log("[3D] 请先选择文件以读取波段信息")
            return

        z_idx = self._z_band_combo.currentIndex()
        if z_idx < 0:
            return

        auto = self._auto_scale.currentIndex() == 0
        params = {
            "path":        path,
            "z_band_idx":  z_idx,
            "z_transform": self._z_transform.currentText(),
            "z_auto_scale": auto,
            "z_scale":     self._z_scale_spin.value(),
            "max_pts":     self._max_pts.value(),
        }

        self._render_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._status.setText("正在计算...")

        self._worker = Surface3DWorker(params)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_done)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _on_progress(self, pct: int, msg: str):
        self._progress.setValue(pct)
        self._status.setText(msg)

    def _on_done(self, data: dict):
        self._render_btn.setEnabled(True)
        self._progress.setVisible(False)

        if not self._canvas:
            self._canvas = Surface3DCanvas()
        self._canvas.render(data, self._colormap.currentText())

        z_name = data.get("z_band_name", "")
        lo, hi = data.get("z_raw_range", (0, 0))
        scale  = data.get("z_scale", 1.0)
        self._status.setText(
            f"渲染完成  |  {z_name}  [{lo:.3g}, {hi:.3g}]  ×{scale:.2f}"
        )
        self.ctx.log(f"[3D] 渲染完成 波段={z_name} 拉伸={scale:.2f}")
        self.ctx.events.publish("status", f"三维渲染完成: {z_name}")

    def _on_fail(self, msg: str):
        self._render_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._status.setText("渲染失败")
        self.ctx.log(f"[3D] 渲染失败:\n{msg}")

"""
极地海冰多参数综合反演平台 — 插件开发标准模板
==============================================

【快速开始】
1. 复制整个 _template 目录，改名为你的插件 ID（如 ice_thickness）
2. 修改 plugin.json：id / name / description / author / requires
3. 在 _AlgorithmWorker.run() 中替换为你的算法逻辑
4. 在 _build_panel() 中调整输入参数控件
5. 在 _on_done() 中决定结果如何展示（地图叠加 / 图表 / 表格）

【接口规范概览】
    必须实现: on_load / on_unload / get_panel
    可选实现: get_viz_tabs / get_stats

【上下文对象 ctx 提供的能力】
    ctx.map         — MapWidget，地图操作（见下方 MapWidget API）
    ctx.log(msg)    — 向底部日志面板输出一条消息
    ctx.events      — EventBus，发布全局事件

【EventBus 可用事件】
    ctx.events.publish("status",   "消息文本")   # 更新状态栏文字
    ctx.events.publish("progress", 75)            # 更新进度条（0-100，负数隐藏）

【MapWidget 常用 API】
    ctx.map.add_polyline(layer_id, [(lat,lon),...], color="#00C4E8", weight=2)
    ctx.map.add_markers(layer_id, [{"lat":..,"lng":..,"radius":4,"popup":".."},...])
    ctx.map.add_image_overlay(layer_id, data_url, south, west, north, east, opacity=0.8)
    ctx.map.remove_layer(layer_id)
    ctx.map.clear_all()
    ctx.map.set_view(lat, lon, zoom)
    ctx.map.map_clicked   — pyqtSignal(float, float)，点击地图时触发

【信号命名注意】
    QThread 子类中 **不能** 定义名为 finished 的自定义信号！
    QThread 已有内置 finished 信号（线程结束时自动 emit）。
    命名冲突会导致线程销毁时 SIGABRT 崩溃。
    请使用其他名称，如 result_ready / done / succeeded。
"""

import os
import sys

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from plugins.base import BasePlugin


# ─────────────────────────────────────────────────────────────────────────────
#  算法工作线程
#  在此处替换为你的核心算法逻辑
# ─────────────────────────────────────────────────────────────────────────────

class _AlgorithmWorker(QThread):
    """
    将耗时计算放在子线程，避免阻塞 UI。

    信号：
        progress(int, str)   — 进度百分比 + 状态描述，供面板进度条展示
        result_ready(dict)   — 算法完成，携带结果字典
        failed(str)          — 算法异常，携带 traceback 字符串

    注意：result_ready 不能命名为 finished（会与 QThread.finished 冲突）。
    """
    progress     = pyqtSignal(int, str)
    result_ready = pyqtSignal(dict)
    failed       = pyqtSignal(str)

    def __init__(self, params: dict):
        """
        params 由 Plugin._run() 构造并传入，包含所有用户在面板中填写的参数。
        建议所有参数以 dict 形式传入，便于扩展且无需修改构造函数签名。
        """
        super().__init__()
        self.params = params

    def run(self):
        """
        【必须替换】在此处实现你的算法逻辑。

        输入（通过 self.params 获取）：
            input_file  : str   — 输入数据文件路径
            output_file : str   — 输出结果保存路径（可选，也可在内存中返回）
            + 其他用户自定义参数

        输出（通过 result_ready 信号发出）：
            result 字典应包含以下可选键（供 _on_done 读取后展示到地图/图表）：
            {
                "data"        : np.ndarray,    # 二维结果数组（灰度/彩色）
                "bounds"      : (S, W, N, E),  # 地理范围（十进制度）
                "output_file" : str,           # 保存的文件路径
                "stats"       : dict,          # 统计信息 {key: value}
                "message"     : str,           # 成功消息
            }
            未用到的键可以省略。
        """
        try:
            # ── 阶段 1：读取输入 ──────────────────────────────────────────
            self.progress.emit(10, "读取输入数据...")
            input_file = self.params["input_file"]

            # 示例：用 rasterio 读取 GeoTIFF
            try:
                import rasterio
                with rasterio.open(input_file) as src:
                    data   = src.read(1).astype(np.float32)
                    nodata = src.nodata
                    bounds = (
                        src.bounds.bottom, src.bounds.left,
                        src.bounds.top,    src.bounds.right,
                    )
                    if nodata is not None:
                        data[data == nodata] = np.nan
            except ImportError:
                # rasterio 不可用时的极简回退
                data   = np.random.rand(256, 256).astype(np.float32)
                bounds = (-90.0, -180.0, 90.0, 180.0)

            # ── 阶段 2：核心算法 ──────────────────────────────────────────
            self.progress.emit(40, "运行反演算法...")

            # ★ 在此替换为你的算法 ★
            threshold = float(self.params.get("threshold", 0.5))
            result_data = np.where(data > threshold, data, np.nan)

            # ── 阶段 3：保存结果（可选）─────────────────────────────────
            self.progress.emit(80, "保存结果...")
            output_file = self.params.get("output_file", "")
            if output_file:
                try:
                    import rasterio
                    from rasterio.transform import from_bounds
                    h, w = result_data.shape
                    transform = from_bounds(
                        bounds[1], bounds[0], bounds[3], bounds[2], w, h
                    )
                    with rasterio.open(
                        output_file, "w", driver="GTiff",
                        height=h, width=w, count=1,
                        dtype=result_data.dtype,
                        crs="EPSG:4326", transform=transform,
                    ) as dst:
                        dst.write(result_data, 1)
                except Exception as e:
                    print(f"[模板插件] 保存结果失败: {e}")

            # ── 阶段 4：发出结果 ──────────────────────────────────────────
            self.progress.emit(100, "算法完成")
            self.result_ready.emit({
                "data":        result_data,
                "bounds":      bounds,
                "output_file": output_file,
                "stats": {
                    "有效像元数":  int(np.sum(~np.isnan(result_data))),
                    "均值":        float(np.nanmean(result_data)),
                    "最大值":      float(np.nanmax(result_data)),
                    "最小值":      float(np.nanmin(result_data)),
                },
                "message": f"算法完成，有效像元 {int(np.sum(~np.isnan(result_data)))}",
            })

        except Exception:
            import traceback
            self.failed.emit(traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
#  插件主类（Plugin 类名固定，平台通过 importlib 直接实例化）
# ─────────────────────────────────────────────────────────────────────────────

class Plugin(BasePlugin):
    """
    插件类名必须为 Plugin，不可更改。
    平台通过 `mod.Plugin()` 创建实例，再调用 on_load(ctx)。
    """

    # 地图图层 ID，用于 remove_layer 时精确清除本插件的图层
    LAYER_ID = "template_result_layer"

    # ── 生命周期 ─────────────────────────────────────────────────────────────

    def on_load(self, ctx):
        """
        插件加载时调用（主线程）。
        存储上下文，初始化状态，可订阅事件。
        """
        self.ctx     = ctx
        self._panel  = None
        self._canvas = None   # 如有图表 Tab，在此初始化
        self._worker = None
        ctx.log(f"[{self.name}] 已加载")

    def on_unload(self):
        """
        插件卸载时调用（主线程）。
        必须：停止后台线程、清除地图图层、释放 Qt 对象。
        """
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()
        self.ctx.map.remove_layer(self.LAYER_ID)
        self.ctx.log(f"[{self.name}] 已卸载")

    # ── 界面构建 ─────────────────────────────────────────────────────────────

    def get_panel(self) -> QWidget:
        """
        返回插件控制面板 Widget，将被注入右侧插件工作区 Tab。
        懒加载：第一次调用时才构建，之后复用同一实例。
        """
        if not self._panel:
            self._panel = self._build_panel()
        return self._panel

    def get_viz_tabs(self) -> list:
        """
        返回额外的可视化 Tab，格式为 [("Tab名称", QWidget), ...]。
        这些 Tab 将注入中央视图区（地图 Tab 旁边）。
        若不需要额外视图，返回空列表 []（如浮动面板插件）。
        """
        # 示例：返回一个图表面板（如果你需要的话）
        # if not self._canvas:
        #     self._canvas = _ResultCanvas()
        # return [("反演结果", self._canvas)]
        return []

    # ── 面板构建（可按需增减控件）────────────────────────────────────────────

    def _build_panel(self) -> QWidget:
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        # 标题
        title = QLabel(self.name)
        title.setProperty("title", True)
        lay.addWidget(title)

        desc = QLabel("在这里添加插件功能简介")
        desc.setProperty("subtitle", True)
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # ── 输入参数组 ─────────────────────────────────────────────────────
        grp_in = QGroupBox("输入数据")
        f_in = QFormLayout(grp_in)

        # 文件选择
        self._input_edit = QLineEdit()
        self._input_edit.setPlaceholderText("选择输入 GeoTIFF 文件...")
        btn_browse = QPushButton("浏览")
        btn_browse.setFixedWidth(60)
        btn_browse.setProperty("secondary", True)
        btn_browse.clicked.connect(self._browse_input)
        row = QHBoxLayout()
        row.addWidget(self._input_edit)
        row.addWidget(btn_browse)
        f_in.addRow("输入文件:", row)

        # 输出路径（可选，自动生成）
        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("留空则不保存到磁盘")
        f_in.addRow("输出路径:", self._output_edit)
        lay.addWidget(grp_in)

        # ── 算法参数组（按需增减）─────────────────────────────────────────
        grp_params = QGroupBox("算法参数")
        f_p = QFormLayout(grp_params)

        # 示例：数值参数
        self._threshold_spin = QDoubleSpinBox()
        self._threshold_spin.setRange(0.0, 1.0)
        self._threshold_spin.setSingleStep(0.05)
        self._threshold_spin.setValue(0.5)
        f_p.addRow("阈值:", self._threshold_spin)

        # 示例：下拉选择
        self._colormap_combo = QComboBox()
        self._colormap_combo.addItems([
            "viridis", "plasma", "inferno", "Blues", "RdYlBu_r", "coolwarm"
        ])
        f_p.addRow("色彩映射:", self._colormap_combo)

        # 示例：复选框
        self._normalize_chk = QCheckBox("归一化输出（映射到 [0, 1]）")
        f_p.addRow("", self._normalize_chk)

        lay.addWidget(grp_params)

        # ── 进度 & 状态 ────────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        lay.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setProperty("subtitle", True)
        self._status.setWordWrap(True)
        lay.addWidget(self._status)

        # ── 操作按钮 ───────────────────────────────────────────────────────
        self._run_btn = QPushButton("运行算法")
        self._run_btn.clicked.connect(self._run)
        lay.addWidget(self._run_btn)

        btn_clear = QPushButton("清除图层")
        btn_clear.setProperty("secondary", True)
        btn_clear.clicked.connect(self._clear)
        lay.addWidget(btn_clear)

        lay.addStretch()
        return root

    # ── 事件处理 ─────────────────────────────────────────────────────────────

    def _browse_input(self):
        path, _ = QFileDialog.getOpenFileName(
            self._panel, "选择输入文件", "",
            "GeoTIFF (*.tif *.tiff);;NetCDF (*.nc);;所有文件 (*)"
        )
        if path:
            self._input_edit.setText(path)
            # 自动生成输出路径
            base, _ = os.path.splitext(path)
            self._output_edit.setText(base + "_result.tif")

    def _run(self):
        """收集参数 → 启动后台线程。"""
        input_file = self._input_edit.text().strip()
        if not input_file or not os.path.exists(input_file):
            self.ctx.log(f"[{self.name}] 请选择有效的输入文件")
            return

        # 如果上一次任务还在运行，先终止
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()

        params = {
            "input_file":  input_file,
            "output_file": self._output_edit.text().strip(),
            "threshold":   self._threshold_spin.value(),
            "colormap":    self._colormap_combo.currentText(),
            "normalize":   self._normalize_chk.isChecked(),
        }

        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._status.setText("正在运行...")

        self._worker = _AlgorithmWorker(params)
        self._worker.progress.connect(self._on_progress)
        self._worker.result_ready.connect(
            lambda res: self._on_done(res, params)
        )
        self._worker.failed.connect(self._on_fail)
        # QThread.finished（无参内置信号）：run() 结束时自动 emit，安全销毁线程
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_progress(self, pct: int, msg: str):
        self._progress.setValue(pct)
        self._status.setText(msg)
        self.ctx.events.publish("progress", pct)
        self.ctx.events.publish("status", f"[{self.name}] {msg}")

    def _on_done(self, result: dict, params: dict):
        """算法完成后，将结果叠加到地图并更新状态。"""
        self._run_btn.setEnabled(True)
        self._progress.setVisible(False)
        self.ctx.events.publish("progress", -1)   # 隐藏状态栏进度条

        data   = result.get("data")
        bounds = result.get("bounds", (-90, -180, 90, 180))

        # ── 叠加到地图（如果有二维栅格结果）─────────────────────────────
        if data is not None:
            try:
                from ui.map_widget import array_to_data_url   # 平台内置工具函数
                data_url = array_to_data_url(data, params["colormap"])
                self.ctx.map.add_image_overlay(
                    self.LAYER_ID, data_url,
                    bounds[0], bounds[1], bounds[2], bounds[3],
                    opacity=0.8,
                )
            except Exception as e:
                self.ctx.log(f"[{self.name}] 地图叠加失败: {e}")

        # ── 统计信息日志 ──────────────────────────────────────────────────
        stats = result.get("stats", {})
        for k, v in stats.items():
            self.ctx.log(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

        msg = result.get("message", "算法完成")
        self._status.setText(msg)
        self.ctx.log(f"[{self.name}] {msg}")
        self.ctx.events.publish("status", f"{self.name}: {msg}")

    def _on_fail(self, tb: str):
        self._run_btn.setEnabled(True)
        self._progress.setVisible(False)
        self.ctx.events.publish("progress", -1)
        self._status.setText("算法执行失败")
        self.ctx.log(f"[{self.name}] 失败:\n{tb}")

    def _clear(self):
        self.ctx.map.remove_layer(self.LAYER_ID)
        self._status.setText("图层已清除")

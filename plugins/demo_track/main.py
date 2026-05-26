"""
测线数据可视化演示插件 (2.5D)
加载 CSV 测线文件 → 地图上显示连线 → 单击点位，
在地图右下角弹出浮动面板显示剖面图与属性信息。

CSV 格式：lat,lon,[depth,[value1,...]]
"""

import os
import sys

import numpy as np
from PyQt6.QtCore import QEvent, Qt, QObject
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QFrame, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from plugins.base import BasePlugin

try:
    import matplotlib
    matplotlib.rcParams['font.sans-serif'] = [
        'Arial Unicode MS', 'PingFang SC', 'Heiti TC', 'SimHei', 'DejaVu Sans'
    ]
    matplotlib.rcParams['axes.unicode_minus'] = False
    matplotlib.use("QtAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

LAYER_TRACK   = "track_line"
LAYER_MARKERS = "track_markers"


# ─────────────────────────────────────────────────────────────────────────────
#  悬浮剖面面板
# ─────────────────────────────────────────────────────────────────────────────

class _ResizeFilter(QObject):
    """监听父 Widget 的 Resize 事件，通知 overlay 重新定位"""
    def __init__(self, overlay):
        super().__init__(overlay)
        self._overlay = overlay

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            self._overlay._reposition()
        return False


class ProfileOverlay(QFrame):
    """固定于地图右下角的浮动剖面/属性面板"""

    W, H = 300, 260

    def __init__(self, parent_map: QWidget):
        super().__init__(parent_map)
        self.setObjectName("profile_overlay")
        self.setFixedSize(self.W, self.H)

        # 深色卡片外观
        self.setStyleSheet("""
            QFrame#profile_overlay {
                background: #0F1E33;
                border: 1px solid rgba(0,196,232,0.55);
                border-radius: 8px;
            }
            QLabel { color: #A8C4DC; font-size: 11px; }
            QLabel#ov_title { color: #E0EEF8; font-size: 12px; font-weight: bold; }
            QLabel#ov_pos   { color: #55D4F8; font-size: 11px; font-family: monospace; }
            QPushButton#ov_close {
                background: transparent;
                color: #7A9CB8;
                border: none;
                font-size: 14px;
                padding: 0 2px;
                min-width: 20px;
            }
            QPushButton#ov_close:hover { color: #EF4444; }
            QTableWidget {
                background: transparent;
                border: none;
                color: #A8C4DC;
                font-size: 10px;
                gridline-color: rgba(255,255,255,0.06);
            }
            QHeaderView::section {
                background: rgba(255,255,255,0.05);
                color: #7A9CB8;
                border: none;
                font-size: 10px;
                padding: 2px 4px;
            }
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        # 标题行
        title_row = QHBoxLayout()
        self._title = QLabel("测线点位信息")
        self._title.setObjectName("ov_title")
        close_btn = QPushButton("✕")
        close_btn.setObjectName("ov_close")
        close_btn.setFixedSize(20, 20)
        close_btn.clicked.connect(self.hide)
        title_row.addWidget(self._title)
        title_row.addStretch()
        title_row.addWidget(close_btn)
        lay.addLayout(title_row)

        # 坐标显示
        self._pos_label = QLabel("—")
        self._pos_label.setObjectName("ov_pos")
        lay.addWidget(self._pos_label)

        # 剖面图
        if HAS_MPL:
            fig, self._ax = plt.subplots(figsize=(2.8, 1.5))
            fig.patch.set_facecolor("#0A1622")
            self._ax.set_facecolor("#0A1622")
            self._ax.tick_params(colors="#4A7090", labelsize=7)
            for sp in self._ax.spines.values():
                sp.set_color("#1A3050")
            self._canvas = FigureCanvasQTAgg(fig)
            self._canvas.setMinimumHeight(110)
            lay.addWidget(self._canvas, stretch=1)
        else:
            lay.addWidget(QLabel("需安装 matplotlib"), stretch=1)

        # 简要属性（2行）
        self._attr1 = QLabel("")
        self._attr2 = QLabel("")
        lay.addWidget(self._attr1)
        lay.addWidget(self._attr2)

        # 安装事件过滤器以跟随父窗口大小变化
        self._filter = _ResizeFilter(self)
        parent_map.installEventFilter(self._filter)
        self.raise_()
        self.hide()

    def _reposition(self):
        p = self.parent()
        if p:
            margin = 12
            x = p.width()  - self.W - margin
            y = p.height() - self.H - margin - 22  # 22 = coords bar height
            self.move(x, y)

    def showEvent(self, event):
        self._reposition()
        super().showEvent(event)

    def update_point(self, point_data: dict):
        lat = point_data.get("lat", 0)
        lon = point_data.get("lon", 0)
        self._pos_label.setText(f"{lat:.4f}° N   {lon:.4f}° E")

        # 取前两个标量属性（排除 lat/lon/profile）
        attrs = [
            (k, v) for k, v in point_data.items()
            if k not in ("lat", "lon", "profile") and isinstance(v, (int, float))
        ]
        for i, lbl in enumerate([self._attr1, self._attr2]):
            if i < len(attrs):
                k, v = attrs[i]
                lbl.setText(f"{k}: {v:.4f}" if isinstance(v, float) else f"{k}: {v}")
            else:
                lbl.setText("")

        # 剖面图
        if HAS_MPL:
            profile = point_data.get("profile")
            self._ax.clear()
            self._ax.set_facecolor("#0A1622")
            self._ax.tick_params(colors="#4A7090", labelsize=7)
            for sp in self._ax.spines.values():
                sp.set_color("#1A3050")
            if profile is not None:
                self._ax.plot(profile, color="#00C4E8", linewidth=1.2)
                self._ax.fill_between(range(len(profile)), profile,
                                      alpha=0.15, color="#00C4E8")
            self._ax.set_xlabel("采样", fontsize=7, color="#4A7090")
            self._ax.set_ylabel("值", fontsize=7, color="#4A7090")
            self._ax.grid(True, alpha=0.15, linewidth=0.5)
            self._ax.figure.tight_layout(pad=0.4)
            self._canvas.draw()

        self.show()
        self.raise_()


# ─────────────────────────────────────────────────────────────────────────────
#  插件本体
# ─────────────────────────────────────────────────────────────────────────────

class Plugin(BasePlugin):

    def on_load(self, ctx):
        self.ctx = ctx
        self._panel = None
        self._track_data: list[dict] = []
        self._overlay = ProfileOverlay(ctx.map)
        ctx.map.map_clicked.connect(self._on_map_click)
        ctx.log(f"[{self.name}] 已加载")

    def on_unload(self):
        try:
            self.ctx.map.map_clicked.disconnect(self._on_map_click)
        except Exception:
            pass
        self.ctx.map.remove_layer(LAYER_TRACK)
        self.ctx.map.remove_layer(LAYER_MARKERS)
        if self._overlay:
            self._overlay.deleteLater()
            self._overlay = None
        self.ctx.log(f"[{self.name}] 已卸载")

    def get_panel(self) -> QWidget:
        if not self._panel:
            self._panel = self._build_panel()
        return self._panel

    def get_viz_tabs(self) -> list:
        # 剖面信息以悬浮面板形式显示在地图上，不占用中央 Tab
        return []

    # ── 面板 ──────────────────────────────────────────────────────────────

    def _build_panel(self) -> QWidget:
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        title = QLabel("测线数据可视化")
        title.setProperty("title", True)
        lay.addWidget(title)

        grp = QGroupBox("数据加载")
        form = QFormLayout(grp)

        self._csv_edit = QLineEdit()
        self._csv_edit.setPlaceholderText("CSV 测线文件...")
        btn = QPushButton("浏览")
        btn.setFixedWidth(60)
        btn.setProperty("secondary", True)
        btn.clicked.connect(self._browse_csv)
        row = QHBoxLayout()
        row.addWidget(self._csv_edit)
        row.addWidget(btn)
        form.addRow("测线文件:", row)

        self._color_col = QComboBox()
        self._color_col.addItem("（按索引着色）")
        form.addRow("颜色列:", self._color_col)
        lay.addWidget(grp)

        grp2 = QGroupBox("显示设置")
        f2 = QFormLayout(grp2)
        self._track_color = QComboBox()
        self._track_color.addItems(["#00C4E8", "#E53935", "#FB8C00", "#7B1FA2", "#37474F"])
        f2.addRow("轨迹颜色:", self._track_color)
        lay.addWidget(grp2)

        self._status = QLabel("未加载数据")
        self._status.setProperty("subtitle", True)
        lay.addWidget(self._status)

        btn_load = QPushButton("加载并显示")
        btn_load.clicked.connect(self._load_and_show)
        lay.addWidget(btn_load)

        btn_clear = QPushButton("清除图层")
        btn_clear.setProperty("secondary", True)
        btn_clear.clicked.connect(self._clear)
        lay.addWidget(btn_clear)

        lay.addStretch()
        return root

    def _browse_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self._panel, "选择测线CSV文件", "", "CSV文件 (*.csv);;所有文件 (*)"
        )
        if path:
            self._csv_edit.setText(path)
            self._preview_columns(path)

    def _preview_columns(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                header = f.readline().strip().split(",")
            self._color_col.clear()
            self._color_col.addItem("（按索引着色）")
            for col in header:
                self._color_col.addItem(col.strip())
        except Exception:
            pass

    def _load_and_show(self):
        path = self._csv_edit.text().strip()
        if not path or not os.path.exists(path):
            self.ctx.log("[测线] 请选择有效的CSV文件")
            return
        try:
            self._track_data = self._parse_csv(path)
            self._show_on_map()
            self._status.setText(f"已加载 {len(self._track_data)} 个点位")
            self.ctx.log(f"[测线] 加载 {len(self._track_data)} 个点  点击地图点位查看剖面")
        except Exception as e:
            self.ctx.log(f"[测线] 加载失败: {e}")

    def _parse_csv(self, path: str) -> list[dict]:
        rows = []
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if not lines:
            return rows
        header = [h.strip() for h in lines[0].strip().split(",")]
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            vals = line.split(",")
            rec: dict = {}
            for i, col in enumerate(header):
                if i < len(vals):
                    try:
                        rec[col] = float(vals[i])
                    except ValueError:
                        rec[col] = vals[i]
            for lat_key in ("lat", "latitude", "纬度", "LAT"):
                if lat_key in rec:
                    rec["lat"] = float(rec[lat_key])
                    break
            for lon_key in ("lon", "longitude", "经度", "LON", "lng"):
                if lon_key in rec:
                    rec["lon"] = float(rec[lon_key])
                    break
            if "depth" in rec:
                depth = float(rec["depth"])
                rec["profile"] = np.sin(np.linspace(0, np.pi, 100)) * depth
            rows.append(rec)
        return rows

    def _show_on_map(self):
        if not self._track_data:
            return
        color = self._track_color.currentText()
        points = [(r["lat"], r["lon"]) for r in self._track_data
                  if "lat" in r and "lon" in r]
        self.ctx.map.add_polyline(LAYER_TRACK, points, color=color, weight=2)

        markers = []
        for r in self._track_data:
            if "lat" not in r or "lon" not in r:
                continue
            lines = []
            for k, v in r.items():
                if isinstance(v, (list, np.ndarray)):
                    continue
                val_str = f"{v:.3f}" if isinstance(v, float) else str(v)
                lines.append(f"<b>{k}</b>: {val_str}")
            popup = "<br>".join(lines)
            markers.append({
                "lat": r["lat"], "lng": r["lon"],
                "radius": 4, "color": color, "fill": color,
                "popup": popup,
            })
        self.ctx.map.add_markers(LAYER_MARKERS, markers)

    def _on_map_click(self, lat: float, lon: float):
        if not self._track_data or not self._overlay:
            return
        pts = [(r.get("lat", 9999), r.get("lon", 9999)) for r in self._track_data]
        dists = [(lat - p[0]) ** 2 + (lon - p[1]) ** 2 for p in pts]
        idx = int(np.argmin(dists))
        if dists[idx] < 1.0:
            self._overlay.update_point(self._track_data[idx])

    def _clear(self):
        self.ctx.map.remove_layer(LAYER_TRACK)
        self.ctx.map.remove_layer(LAYER_MARKERS)
        self._track_data = []
        if self._overlay:
            self._overlay.hide()
        self._status.setText("已清除")

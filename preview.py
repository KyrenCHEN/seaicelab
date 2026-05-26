"""
UI 快速预览脚本
==============
单独显示某个面板/插件，不启动完整平台，启动极快。

用法（命令行）：
    python preview.py data_panel
    python preview.py demo_3d
    python preview.py demo_2d
    python preview.py algo_library
    python preview.py startup

VSCode：在 Run & Debug 下拉框选择对应的"👁 预览：xxx"配置，按 F5。
"""

import sys
import os

# 让子模块能正常 import
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from PyQt6.QtWidgets import QApplication, QMainWindow, QDockWidget, QLabel
from PyQt6.QtCore import Qt

target = sys.argv[1] if len(sys.argv) > 1 else "data_panel"

app = QApplication(sys.argv)

# ── 加载样式表（和主程序一致） ───────────────────────────────────────────────
try:
    from core import config as cfg
    style_path = os.path.join(ROOT, "ui", "style.qss")
    if os.path.exists(style_path):
        with open(style_path, encoding="utf-8") as f:
            app.setStyleSheet(f.read())
except Exception as e:
    print(f"[预览] 样式表加载失败（可忽略）: {e}")

# ── 模拟最小上下文 ───────────────────────────────────────────────────────────
class FakeMap:
    def add_geotiff_layer(self, *a, **k): pass
    def add_geojson(self, *a, **k): pass
    def remove_layer(self, *a, **k): pass
    def clear_all(self): pass
    def set_basemap(self, *a): pass
    def set_layer_opacity(self, *a): pass
    def add_image_overlay(self, *a, **k): pass

class FakeEvents:
    def publish(self, *a, **k): pass
    def subscribe(self, *a, **k): pass

class FakeCtx:
    map    = FakeMap()
    events = FakeEvents()
    data   = None
    def log(self, msg): print(msg)

ctx = FakeCtx()


# ── 各面板预览 ───────────────────────────────────────────────────────────────

def preview_data_panel():
    from core.data_manager import DataManager
    from ui.data_panel import DataPanel

    dm = DataManager()
    # 插入几条假数据，方便看效果
    dm.add("/tmp/demo_ice.tif",  name="冰厚度图",   dtype="GeoTIFF")
    dm.add("/tmp/demo_sic.nc",   name="海冰密集度",  dtype="NetCDF")
    dm.add("/tmp/track.csv",     name="航迹数据",    dtype="CSV")

    ctx.data = dm
    panel = DataPanel(dm, print)
    panel.setWindowTitle("预览：数据面板")
    panel.resize(280, 600)
    panel.show()
    return panel


def preview_plugin(plugin_dir: str):
    """通用插件面板预览。"""
    from core.data_manager import DataManager
    dm = DataManager()
    dm.add("/tmp/demo_ice.tif", name="冰厚度图", dtype="GeoTIFF")
    ctx.data = dm

    sys.path.insert(0, os.path.join(ROOT, "plugins", plugin_dir))
    import importlib, importlib.util
    spec = importlib.util.spec_from_file_location(
        "plugin_main",
        os.path.join(ROOT, "plugins", plugin_dir, "main.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    plugin = mod.Plugin()
    plugin.on_load(ctx)

    win = QMainWindow()
    win.setWindowTitle(f"预览：{plugin_dir}")
    win.resize(340, 700)

    panel = plugin.get_panel()
    if panel:
        dock = QDockWidget("面板", win)
        dock.setWidget(panel)
        dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        win.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    # viz tabs（如有）
    for tab_name, tab_widget in plugin.get_viz_tabs():
        win.setCentralWidget(tab_widget)
        break
    else:
        placeholder = QLabel(f"{plugin_dir} 无可视化 Tab")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        win.setCentralWidget(placeholder)

    win.show()
    return win


def preview_startup():
    from ui.startup_dialog import StartupDialog
    dlg = StartupDialog()
    dlg.show()
    return dlg


# ── 路由 ────────────────────────────────────────────────────────────────────
widgets = []   # 防止被 GC

if target == "data_panel":
    widgets.append(preview_data_panel())
elif target == "startup":
    widgets.append(preview_startup())
elif target in ("demo_3d", "demo_2d", "algo_library", "demo_track"):
    widgets.append(preview_plugin(target))
else:
    print(f"未知目标: {target}")
    print("可用: data_panel | startup | demo_3d | demo_2d | algo_library | demo_track")
    sys.exit(1)

sys.exit(app.exec())

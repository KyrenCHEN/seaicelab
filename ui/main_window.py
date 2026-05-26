"""
主窗口
======
仿 QGIS 布局：
    菜单栏 + 工具栏
    左  Dock  : 数据面板
    中央区域  : 地图 / 可视化 Tab
    右  Dock  : 算法工作区（插件面板）
    底  Dock  : 日志
    状态栏    : 工程名 · 坐标 · 进度
"""

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QDockWidget, QFileDialog, QHBoxLayout,
    QLabel, QMainWindow, QMenu, QMessageBox,
    QPlainTextEdit, QProgressBar, QStatusBar,
    QTabWidget, QToolBar, QVBoxLayout, QWidget,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core import config as cfg
from core.data_manager import DataManager
from core.events import bus
from core.plugin_manager import PluginContext, PluginManager
from core.project import DatasetRecord, Project, PROJECT_EXT
from ui.data_panel import DataPanel
from ui.map_widget import MapWidget


class MainWindow(QMainWindow):
    def __init__(self, project: Project | None = None,
                 license_info: dict | None = None):
        super().__init__()

        # ── 核心对象 ────────────────────────────────────────────────────────
        self._project: Project | None = project
        self._dm = DataManager(self)

        self._pm = PluginManager(os.path.join(ROOT, "plugins"))
        self._pm.discover()

        self._map = MapWidget()
        self._ctx = PluginContext(self._map, self._log, bus, self._dm)

        self._plugin_panels: dict[str, QWidget] = {}
        self._analysis_actions: dict[str, object] = {}

        # ── 构建 UI ─────────────────────────────────────────────────────────
        self._build_menu()
        self._build_toolbar()
        self._build_center()
        self._build_left_dock()
        self._build_right_dock()
        self._build_bottom_dock()
        self._build_statusbar()

        # ── 信号 ────────────────────────────────────────────────────────────
        bus.subscribe("status",   self._on_bus_status)
        bus.subscribe("progress", self._on_bus_progress)

        # ── 初始化 ──────────────────────────────────────────────────────────
        self._apply_project(self._project, first_load=True)
        self._update_title()

        self._log("平台就绪。")
        if license_info:
            ltype = "管理员" if license_info.get("type") == "admin" else "授权用户"
            self._log(f"授权状态: {ltype}")

    # ════════════════════════════════════════════════════════════════════════
    #  UI 构建
    # ════════════════════════════════════════════════════════════════════════

    def _build_menu(self):
        mb = self.menuBar()

        # ── 文件 ────────────────────────────────────────────────────────────
        fm = mb.addMenu("文件(&F)")
        fm.addAction("新建工程(&N)…",  self._new_project).setShortcut("Ctrl+N")
        fm.addAction("打开工程(&O)…",  self._open_project).setShortcut("Ctrl+O")
        fm.addAction("保存工程(&S)",   self._save_project).setShortcut("Ctrl+S")
        fm.addAction("工程另存为…",    self._save_project_as)
        fm.addSeparator()
        self._recent_menu = fm.addMenu("最近工程(&R)")
        self._rebuild_recent_menu()
        fm.addSeparator()
        fm.addAction("导出报告…",      self._open_report_dialog)
        fm.addSeparator()
        fm.addAction("退出(&Q)", self.close).setShortcut("Ctrl+Q")

        # ── 数据 ────────────────────────────────────────────────────────────
        # 注意：_data_panel_ref 在 _build_left_dock 中才创建，
        # 但 lambda 是惰性求值，点击时才执行，届时 _data_panel_ref 已存在。
        dm = mb.addMenu("数据(&D)")
        dm.addAction("添加数据文件…", lambda: self._data_panel_ref._add_files())
        dm.addAction("添加数据目录…", lambda: self._data_panel_ref._add_folder())
        dm.addSeparator()
        dm.addAction("移除选中数据",  lambda: self._data_panel_ref._remove_selected())
        dm.addAction("清除全部数据",  self._dm.clear)
        self._data_menu = dm

        # ── 算法 ────────────────────────────────────────────────────────────
        self._algo_menu = mb.addMenu("算法(&A)")
        self._algo_menu.addAction("插件管理器…", self._open_plugin_manager)
        self._algo_menu.addSeparator()
        # 动态插件 Action 在 _on_plugin_loaded 中追加

        # ── 可视化 ──────────────────────────────────────────────────────────
        vm = mb.addMenu("可视化(&V)")
        vm.addAction("清除所有图层", self._map.clear_all)
        vm.addSeparator()
        bm_menu = vm.addMenu("底图")
        for name in MapWidget.basemaps:
            act = bm_menu.addAction(name)
            act.triggered.connect(lambda _, n=name: self._set_basemap(n))

        # ── 视图 ────────────────────────────────────────────────────────────
        wm = mb.addMenu("视图(&W)")
        self._act_data_panel   = wm.addAction("数据面板")
        self._act_data_panel.setCheckable(True)
        self._act_data_panel.setChecked(True)
        self._act_data_panel.triggered.connect(
            lambda c: self._left_dock.setVisible(c))

        self._act_algo_panel   = wm.addAction("算法工作区")
        self._act_algo_panel.setCheckable(True)
        self._act_algo_panel.setChecked(True)
        self._act_algo_panel.triggered.connect(
            lambda c: self._right_dock.setVisible(c))

        self._act_log_panel    = wm.addAction("日志面板")
        self._act_log_panel.setCheckable(True)
        self._act_log_panel.setChecked(True)
        self._act_log_panel.triggered.connect(
            lambda c: self._log_dock.setVisible(c))

        # ── 工程 ────────────────────────────────────────────────────────────
        pm = mb.addMenu("工程(&P)")
        pm.addAction("工程设置…",        self._project_settings)
        pm.addAction("在 Finder 中打开工作目录", self._open_work_dir)

        # ── 帮助 ────────────────────────────────────────────────────────────
        hm = mb.addMenu("帮助(&H)")
        hm.addAction("硬件 ID / 授权信息…", self._show_license_info)
        hm.addSeparator()
        hm.addAction("关于", self._about)

    def _build_toolbar(self):
        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        tb.setObjectName("main_toolbar")
        self.addToolBar(tb)

        tb.addAction("🆕", self._new_project).setToolTip("新建工程")
        tb.addAction("📂", self._open_project).setToolTip("打开工程")
        tb.addAction("💾", self._save_project).setToolTip("保存工程")
        tb.addSeparator()
        tb.addAction("➕", lambda: self._data_panel_ref._add_files()).setToolTip("添加数据")
        tb.addSeparator()
        tb.addWidget(QLabel("  底图:"))
        self._basemap_combo = QComboBox()
        self._basemap_combo.addItems(MapWidget.basemaps)
        self._basemap_combo.setFixedWidth(140)
        self._basemap_combo.currentTextChanged.connect(self._set_basemap)
        tb.addWidget(self._basemap_combo)
        tb.addSeparator()
        tb.addAction("✕ 清除图层", self._map.clear_all)
        tb.addSeparator()
        tb.addAction("📄 导出报告", self._open_report_dialog)

    def _build_center(self):
        self._center_tabs = QTabWidget()
        self._center_tabs.setObjectName("center_tabs")
        self._center_tabs.setTabPosition(QTabWidget.TabPosition.South)
        self._center_tabs.tabBar().setExpanding(False)
        self._center_tabs.addTab(self._map, "🗺  地图视图")
        self.setCentralWidget(self._center_tabs)

    def _build_left_dock(self):
        dock = QDockWidget("数据面板", self)
        dock.setObjectName("left_dock")
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea
        )
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        dock.setMinimumWidth(230)

        panel = DataPanel(self._dm, self._log, self)
        self._data_panel_ref = panel   # 让菜单 lambda 可以访问
        panel.show_on_map.connect(self._visualize_dataset)
        panel.hide_from_map.connect(
            lambda ds_id: self._map.remove_layer(f"data_{ds_id}")
        )
        dock.setWidget(panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self._left_dock = dock

        dock.visibilityChanged.connect(
            lambda v: self._act_data_panel.setChecked(v)
            if hasattr(self, "_act_data_panel") else None
        )

    def _build_right_dock(self):
        dock = QDockWidget("算法工作区", self)
        dock.setObjectName("right_dock")
        dock.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea |
            Qt.DockWidgetArea.LeftDockWidgetArea
        )
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        dock.setMinimumWidth(300)

        self._plugin_tab = QTabWidget()
        self._plugin_tab.setTabPosition(QTabWidget.TabPosition.North)
        self._plugin_tab.setTabsClosable(True)
        self._plugin_tab.tabBar().setExpanding(False)
        self._plugin_tab.tabBar().setUsesScrollButtons(True)
        self._plugin_tab.tabCloseRequested.connect(self._on_plugin_tab_close)

        self._plugin_placeholder = QLabel(
            "算法工作区为空\n\n使用「算法 → 插件管理器」\n加载功能模块"
        )
        self._plugin_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._plugin_placeholder.setProperty("subtitle", True)
        self._plugin_tab.addTab(self._plugin_placeholder, "")
        self._plugin_tab.tabBar().setTabButton(
            0, self._plugin_tab.tabBar().ButtonPosition.RightSide, None
        )

        dock.setWidget(self._plugin_tab)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self._right_dock = dock

        dock.visibilityChanged.connect(
            lambda v: self._act_algo_panel.setChecked(v)
            if hasattr(self, "_act_algo_panel") else None
        )

    def _build_bottom_dock(self):
        dock = QDockWidget("日志", self)
        dock.setObjectName("log_dock")
        dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self._log_edit = QPlainTextEdit()
        self._log_edit.setObjectName("log_edit")
        self._log_edit.setReadOnly(True)
        self._log_edit.setMaximumBlockCount(2000)
        self._log_edit.setFixedHeight(130)
        dock.setWidget(self._log_edit)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        self._log_dock = dock

        dock.visibilityChanged.connect(
            lambda v: self._act_log_panel.setChecked(v)
            if hasattr(self, "_act_log_panel") else None
        )

    def _build_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)

        self._proj_label   = QLabel("")
        self._proj_label.setStyleSheet("color: #7AA0C0; font-size: 11px;")
        self._status_label = QLabel("就绪")
        self._progress = QProgressBar()
        self._progress.setFixedWidth(160)
        self._progress.setVisible(False)

        sb.addWidget(self._proj_label)
        sb.addWidget(QLabel("  "))
        sb.addWidget(self._status_label)
        sb.addPermanentWidget(self._progress)

    # ════════════════════════════════════════════════════════════════════════
    #  工程管理
    # ════════════════════════════════════════════════════════════════════════

    def _apply_project(self, project: Project | None, first_load: bool = False):
        """切换/加载工程：同步数据集、底图、插件。"""
        # 卸载所有已加载插件
        if not first_load:
            for pid in list(self._pm.get_loaded_ids()):
                self._pm.unload(pid)
                self._on_plugin_unloaded(pid)

        # 清空数据
        self._dm.clear()

        if project:
            # 恢复数据集
            for rec in project.datasets:
                if os.path.exists(rec.path):
                    self._dm.add(rec.path, rec.name, rec.dtype)
                else:
                    self._log(f"[工程] 数据文件缺失，跳过: {rec.path}")

            # 恢复底图
            bm = project.basemap
            if bm in MapWidget.basemaps:
                self._basemap_combo.setCurrentText(bm)
                self._map.set_basemap(bm)

            # 恢复插件
            for pid in project.loaded_plugins:
                if pid in self._pm.get_available():
                    ok, msg = self._pm.load(pid, self._ctx)
                    if ok:
                        self._on_plugin_loaded(pid, save=False)
                    else:
                        self._log(f"[插件] 自动加载失败 {pid}: {msg}")
        else:
            # 无工程：从全局配置恢复上次插件
            for pid in cfg.get("loaded_plugins", []):
                if pid in self._pm.get_available():
                    ok, msg = self._pm.load(pid, self._ctx)
                    if ok:
                        self._on_plugin_loaded(pid, save=False)

        self._project = project
        self._update_title()

    def _snapshot_project_state(self):
        """把当前运行时状态写回 project 对象（保存前调用）。"""
        if not self._project:
            return
        self._project.datasets = [
            DatasetRecord(name=e.name, path=e.path, dtype=e.dtype)
            for e in self._dm.all()
        ]
        self._project.loaded_plugins = self._pm.get_loaded_ids()
        self._project.basemap = self._basemap_combo.currentText()

    def _update_title(self):
        if self._project:
            suffix = "" if self._project.is_saved else " *"
            self.setWindowTitle(
                f"极地海冰多参数综合反演平台  —  {self._project.name}{suffix}"
            )
            self._proj_label.setText(
                f"工程: {self._project.name}"
                + (f"  ({os.path.basename(self._project.file_path)})"
                   if self._project.is_saved else "  [未保存]")
            )
        else:
            self.setWindowTitle("极地海冰多参数综合反演平台 v1.0")
            self._proj_label.setText("无工程")

    def _rebuild_recent_menu(self):
        self._recent_menu.clear()
        recents = cfg.get("recent_projects", [])
        for path in recents:
            if os.path.exists(path):
                act = self._recent_menu.addAction(
                    f"{os.path.basename(path)}  —  {os.path.dirname(path)}"
                )
                act.triggered.connect(lambda _, p=path: self._load_project_file(p))
        if not self._recent_menu.actions():
            na = self._recent_menu.addAction("（暂无最近工程）")
            na.setEnabled(False)

    # ── 工程 Action ─────────────────────────────────────────────────────────

    def _new_project(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "新建工程", "工程名称:", text="未命名工程"
        )
        if not ok or not name.strip():
            return
        work_dir = QFileDialog.getExistingDirectory(self, "选择工作目录")
        if not work_dir:
            return
        self._apply_project(Project.new(name=name.strip(), work_dir=work_dir))
        self._log(f"[工程] 新建工程: {name}")

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开工程", "",
            f"海冰平台工程 (*{PROJECT_EXT});;所有文件 (*)"
        )
        if path:
            self._load_project_file(path)

    def _load_project_file(self, path: str):
        try:
            proj = Project.load(path)
            self._apply_project(proj)
            self._add_recent(path)
            self._rebuild_recent_menu()
            self._log(f"[工程] 已打开: {proj.name}")
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法加载工程文件：\n{e}")

    def _save_project(self):
        if not self._project:
            return self._save_project_as()
        if not self._project.is_saved:
            return self._save_project_as()
        self._snapshot_project_state()
        try:
            self._project.save()
            self._update_title()
            self._log(f"[工程] 已保存: {self._project.file_path}")
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))

    def _save_project_as(self):
        if not self._project:
            QMessageBox.information(self, "提示", "请先新建或打开一个工程。")
            return
        default = os.path.join(
            self._project.work_dir or os.path.expanduser("~"),
            self._project.name + PROJECT_EXT
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "工程另存为", default,
            f"海冰平台工程 (*{PROJECT_EXT});;所有文件 (*)"
        )
        if not path:
            return
        self._snapshot_project_state()
        try:
            self._project.save(path)
            self._add_recent(path)
            self._rebuild_recent_menu()
            self._update_title()
            self._log(f"[工程] 已另存为: {path}")
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))

    def _project_settings(self):
        if not self._project:
            QMessageBox.information(self, "提示", "请先新建或打开一个工程。")
            return
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "工程设置", "工程名称:", text=self._project.name
        )
        if ok and name.strip():
            self._project.name = name.strip()
            self._update_title()

    def _open_work_dir(self):
        if self._project and self._project.work_dir:
            import subprocess
            subprocess.Popen(["open", self._project.work_dir])

    @staticmethod
    def _add_recent(path: str):
        recents = cfg.get("recent_projects", [])
        if path in recents:
            recents.remove(path)
        recents.insert(0, path)
        cfg.set("recent_projects", recents[:12])

    # ════════════════════════════════════════════════════════════════════════
    #  插件管理
    # ════════════════════════════════════════════════════════════════════════

    def _open_plugin_manager(self):
        from ui.plugin_dialog import PluginManagerDialog
        dlg = PluginManagerDialog(self._pm, self._ctx, self)
        dlg.exec()

    def _on_plugin_loaded(self, plugin_id: str, save: bool = True):
        plugin = self._pm.get_plugin(plugin_id)
        if not plugin:
            return

        # 移除占位符
        if (self._plugin_tab.count() == 1
                and self._plugin_tab.widget(0) is self._plugin_placeholder):
            self._plugin_tab.removeTab(0)

        panel = plugin.get_panel()
        if panel:
            self._plugin_panels[plugin_id] = panel
            self._plugin_tab.addTab(panel, plugin.name)
            self._plugin_tab.setCurrentWidget(panel)
            self._right_dock.setVisible(True)

        for tab_name, tab_widget in plugin.get_viz_tabs():
            self._center_tabs.addTab(
                tab_widget, f"{plugin.name} · {tab_name}"
            )

        self._add_analysis_action(plugin_id, plugin.name)
        if save:
            self._save_loaded_plugins()
        self._log(f"[插件] 已加载: {plugin.name}")

    def _on_plugin_unloaded(self, plugin_id: str):
        meta = self._pm.get_available().get(plugin_id, {})
        name = meta.get("name", plugin_id)

        panel = self._plugin_panels.pop(plugin_id, None)
        if panel:
            idx = self._plugin_tab.indexOf(panel)
            if idx >= 0:
                self._plugin_tab.removeTab(idx)

        to_remove = []
        for i in range(self._center_tabs.count()):
            if self._center_tabs.tabText(i).startswith(name + " ·"):
                to_remove.append(i)
        for i in reversed(to_remove):
            w = self._center_tabs.widget(i)
            self._center_tabs.removeTab(i)
            w.deleteLater()

        action = self._analysis_actions.pop(plugin_id, None)
        if action:
            self._algo_menu.removeAction(action)

        if self._plugin_tab.count() == 0:
            self._plugin_tab.addTab(self._plugin_placeholder, "")
            self._plugin_tab.tabBar().setTabButton(
                0, self._plugin_tab.tabBar().ButtonPosition.RightSide, None
            )

        self._save_loaded_plugins()
        self._log(f"[插件] 已卸载: {name}")

    def _on_plugin_tab_close(self, index: int):
        widget = self._plugin_tab.widget(index)
        if widget is self._plugin_placeholder:
            return
        pid = next(
            (k for k, v in self._plugin_panels.items() if v is widget), None
        )
        self._plugin_tab.removeTab(index)

        if self._plugin_tab.count() == 0:
            self._plugin_tab.addTab(self._plugin_placeholder, "")
            self._plugin_tab.tabBar().setTabButton(
                0, self._plugin_tab.tabBar().ButtonPosition.RightSide, None
            )
        if pid and pid in self._analysis_actions:
            self._analysis_actions[pid].setChecked(False)

    def _add_analysis_action(self, plugin_id: str, name: str):
        act = self._algo_menu.addAction(name)
        act.setCheckable(True)
        act.setChecked(True)
        act.triggered.connect(
            lambda checked, pid=plugin_id:
            self._toggle_plugin_panel(pid, checked)
        )
        self._analysis_actions[plugin_id] = act

    def _toggle_plugin_panel(self, plugin_id: str, show: bool):
        panel = self._plugin_panels.get(plugin_id)
        if not panel:
            return
        if show:
            if self._plugin_tab.indexOf(panel) < 0:
                if (self._plugin_tab.count() == 1
                        and self._plugin_tab.widget(0) is self._plugin_placeholder):
                    self._plugin_tab.removeTab(0)
                self._plugin_tab.addTab(
                    panel, self._pm.get_plugin(plugin_id).name
                )
            self._plugin_tab.setCurrentWidget(panel)
            self._right_dock.setVisible(True)
        else:
            idx = self._plugin_tab.indexOf(panel)
            if idx >= 0:
                self._plugin_tab.removeTab(idx)
            if self._plugin_tab.count() == 0:
                self._plugin_tab.addTab(self._plugin_placeholder, "")
                self._plugin_tab.tabBar().setTabButton(
                    0, self._plugin_tab.tabBar().ButtonPosition.RightSide, None
                )

    def _save_loaded_plugins(self):
        cfg.set("loaded_plugins", self._pm.get_loaded_ids())

    # ════════════════════════════════════════════════════════════════════════
    #  底图
    # ════════════════════════════════════════════════════════════════════════

    def _set_basemap(self, name: str):
        self._map.set_basemap(name)
        if self._basemap_combo.currentText() != name:
            self._basemap_combo.setCurrentText(name)

    # ════════════════════════════════════════════════════════════════════════
    #  EventBus 回调
    # ════════════════════════════════════════════════════════════════════════

    def _on_bus_status(self, msg: str):
        self._status_label.setText(msg)

    def _on_bus_progress(self, value):
        if value < 0:
            self._progress.setVisible(False)
        else:
            self._progress.setVisible(True)
            self._progress.setValue(int(value))

    # ════════════════════════════════════════════════════════════════════════
    #  数据可视化
    # ════════════════════════════════════════════════════════════════════════

    def _visualize_dataset(self, ds_id: str):
        """将数据集叠加到地图（仅支持 GeoTIFF / GeoJSON）。"""
        e = self._dm.get(ds_id)
        if not e:
            return

        ext = os.path.splitext(e.path)[1].lower()

        if ext in (".tif", ".tiff"):
            try:
                self._map.add_geotiff_layer(
                    layer_id=f"data_{ds_id}",
                    filepath=e.path,
                    colormap="viridis",
                    opacity=0.8,
                )
                self._log(f"[可视化] GeoTIFF 已叠加到地图: {e.name}")
            except Exception as ex:
                self._log(f"[可视化] GeoTIFF 加载失败: {ex}")

        elif ext in (".geojson", ".json"):
            try:
                import json
                with open(e.path, encoding="utf-8") as f:
                    gj = json.load(f)
                self._map.add_geojson(
                    layer_id=f"data_{ds_id}",
                    geojson=gj,
                    style={"color": "#3388ff", "weight": 2, "fillOpacity": 0.4},
                )
                self._log(f"[可视化] GeoJSON 已叠加到地图: {e.name}")
            except Exception as ex:
                self._log(f"[可视化] GeoJSON 加载失败: {ex}")

        else:
            self._log(f"[可视化] 不支持的格式，跳过: {e.name}  ({ext})")

    # ════════════════════════════════════════════════════════════════════════
    #  工具方法
    # ════════════════════════════════════════════════════════════════════════

    def _log(self, msg: str):
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_edit.appendPlainText(f"[{ts}] {msg}")

    def _open_report_dialog(self):
        from ui.report_dialog import ReportDialog
        dlg = ReportDialog(self._map, self._pm, self)
        dlg.exec()

    def _show_license_info(self):
        from core.license import LicenseManager
        lm = LicenseManager()
        hw = lm.get_hardware_id()
        QMessageBox.information(
            self, "授权信息",
            f"<b>硬件ID：</b><br><tt>{hw}</tt><br><br>"
            f"提供此ID给管理员以生成许可证。"
        )

    def _about(self):
        QMessageBox.about(
            self, "关于",
            "<b>极地海冰多参数综合反演平台</b> v1.0<br><br>"
            "插件式极地遥感数据处理与可视化平台<br>"
            "支持 2D / 2.5D / 3D 多模式可视化<br><br>"
            "技术栈: Python · PyQt6 · Leaflet.js"
        )

    # ── 关闭时保存 ──────────────────────────────────────────────────────────
    def closeEvent(self, event):
        if self._project and self._project.is_saved:
            self._snapshot_project_state()
            try:
                self._project.save()
            except Exception:
                pass
        super().closeEvent(event)

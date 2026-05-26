"""
数据面板（左侧 Dock）
====================
展示当前工程已加载的所有数据集。
支持：添加文件 / 添加目录 / 右键移除 / 属性查看 / Finder 定位。
复选框控制图层地图可见性（勾选=显示，取消=隐藏）。
"""

import os
import subprocess

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView, QFileDialog, QLabel,
    QMenu, QMessageBox, QToolBar,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from core.data_manager import DataManager, DataEntry

_FILE_FILTER = (
    "遥感数据文件 (*.tif *.tiff *.nc *.nc4 *.h5 *.hdf5 *.img *.dat *.csv *.txt);;"
    "GeoTIFF (*.tif *.tiff);;"
    "NetCDF (*.nc *.nc4);;"
    "HDF5 (*.h5 *.hdf5);;"
    "所有文件 (*)"
)

_SCAN_EXTS = {".tif", ".tiff", ".nc", ".nc4", ".h5", ".hdf5", ".img", ".dat", ".csv"}

# 可直接在地图上可视化的扩展名
_MAP_EXTS = {".tif", ".tiff", ".geojson", ".json"}


class DataPanel(QWidget):
    """左侧数据管理面板。"""

    # 勾选复选框 / 双击 / 右键"在地图中显示"时发射
    show_on_map  = pyqtSignal(str)
    # 取消复选框 / 数据被移除时发射（通知 MainWindow 移除图层）
    hide_from_map = pyqtSignal(str)

    def __init__(self, data_manager: DataManager, log_fn, parent=None):
        super().__init__(parent)
        self._dm  = data_manager
        self._log = log_fn
        self._id_to_item: dict[str, QTreeWidgetItem] = {}
        self._build()
        self._connect()

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # 迷你工具栏
        tb = QToolBar()
        tb.setMovable(False)
        tb.setStyleSheet("QToolBar { padding: 2px 6px; }")

        act_add = tb.addAction("＋ 添加")
        act_add.setToolTip("添加数据文件")
        act_add.triggered.connect(self._add_files)

        act_dir = tb.addAction("📂 目录")
        act_dir.setToolTip("扫描并添加整个目录")
        act_dir.triggered.connect(self._add_folder)

        lay.addWidget(tb)

        # 树形列表
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["名称", "类型"])
        # 两列均为 Interactive，用户可以拖动分隔线自由调整宽度
        hdr = self._tree.header()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, hdr.ResizeMode.Interactive)
        hdr.setSectionResizeMode(1, hdr.ResizeMode.Interactive)
        hdr.setMinimumSectionSize(40)
        self._tree.setColumnWidth(0, 150)
        self._tree.setColumnWidth(1, 72)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        # 允许拖拽调整顺序
        self._tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._tree.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._ctx_menu)
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        self._tree.setRootIsDecorated(False)
        lay.addWidget(self._tree)

        # 底部状态栏
        self._status = QLabel("0 个数据集")
        self._status.setProperty("subtitle", True)
        self._status.setContentsMargins(8, 3, 8, 3)
        self._status.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        lay.addWidget(self._status)

    def _connect(self):
        self._dm.dataset_added.connect(self._on_added)
        self._dm.dataset_removed.connect(self._on_removed)
        self._dm.cleared.connect(self._on_cleared)
        self._tree.itemChanged.connect(self._on_item_changed)

    # ── 工具：判断该格式是否支持地图显示 ───────────────────────────────────

    @staticmethod
    def _is_mappable(path: str) -> bool:
        return os.path.splitext(path)[1].lower() in _MAP_EXTS

    # ── 信号响应 ────────────────────────────────────────────────────────────

    def _on_added(self, ds_id: str):
        e = self._dm.get(ds_id)
        if not e:
            return
        item = QTreeWidgetItem([f"{e.icon} {e.name}", e.dtype])
        item.setData(0, Qt.ItemDataRole.UserRole, ds_id)
        item.setToolTip(0, e.path)
        item.setToolTip(1, e.path)

        # 可映射格式：启用复选框；不可映射：禁用复选（但保留行）
        if self._is_mappable(e.path):
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            # 用 blockSignals 避免触发 _on_item_changed
            self._tree.blockSignals(True)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            self._tree.blockSignals(False)
        else:
            # 不可映射格式：不显示复选框
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)

        self._tree.addTopLevelItem(item)
        self._id_to_item[ds_id] = item
        self._refresh_status()

    def _on_removed(self, ds_id: str):
        item = self._id_to_item.pop(ds_id, None)
        if item:
            # 若图层正在地图上显示，通知隐藏
            if item.checkState(0) == Qt.CheckState.Checked:
                self.hide_from_map.emit(ds_id)
            idx = self._tree.indexOfTopLevelItem(item)
            if idx >= 0:
                self._tree.takeTopLevelItem(idx)
        self._refresh_status()

    def _on_cleared(self):
        # 通知所有可见图层隐藏
        for ds_id, item in self._id_to_item.items():
            if item.checkState(0) == Qt.CheckState.Checked:
                self.hide_from_map.emit(ds_id)
        self._tree.clear()
        self._id_to_item.clear()
        self._refresh_status()

    def _on_item_changed(self, item: QTreeWidgetItem, col: int):
        """复选框状态变化 → 显示/隐藏地图图层。"""
        if col != 0:
            return
        ds_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not ds_id:
            return
        if item.checkState(0) == Qt.CheckState.Checked:
            self.show_on_map.emit(ds_id)
        else:
            self.hide_from_map.emit(ds_id)

    # ── 操作 ────────────────────────────────────────────────────────────────

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "添加数据文件", "", _FILE_FILTER
        )
        for p in paths:
            ds_id = self._dm.add(p)
            e = self._dm.get(ds_id)
            self._log(f"[数据] 已加载: {e.name}  [{e.dtype}]")

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择数据目录")
        if not folder:
            return
        count = 0
        for fn in sorted(os.listdir(folder)):
            if os.path.splitext(fn)[1].lower() in _SCAN_EXTS:
                self._dm.add(os.path.join(folder, fn))
                count += 1
        self._log(f"[数据] 从目录导入 {count} 个文件: {os.path.basename(folder)}/")

    def _remove_selected(self):
        for item in self._tree.selectedItems():
            ds_id = item.data(0, Qt.ItemDataRole.UserRole)
            if ds_id:
                self._dm.remove(ds_id)

    def _refresh_status(self):
        n = len(self._dm)
        self._status.setText(f"{n} 个数据集")

    def _on_double_click(self, item: QTreeWidgetItem, _col: int):
        """双击：切换复选框状态（对可映射格式）。"""
        if not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            return
        new = (Qt.CheckState.Unchecked
               if item.checkState(0) == Qt.CheckState.Checked
               else Qt.CheckState.Checked)
        item.setCheckState(0, new)

    # ── 右键菜单 ────────────────────────────────────────────────────────────

    def _ctx_menu(self, pos):
        item = self._tree.itemAt(pos)
        menu = QMenu(self)
        if item:
            ds_id = item.data(0, Qt.ItemDataRole.UserRole)
            e = self._dm.get(ds_id)

            # 仅可映射格式显示地图控制选项
            if e and self._is_mappable(e.path):
                is_visible = item.checkState(0) == Qt.CheckState.Checked
                if is_visible:
                    menu.addAction("🙈 从地图中移除",
                                   lambda: item.setCheckState(0, Qt.CheckState.Unchecked))
                else:
                    menu.addAction("🗺 在地图中显示",
                                   lambda: item.setCheckState(0, Qt.CheckState.Checked))
                menu.addSeparator()

            menu.addAction("移除数据", lambda: self._dm.remove(ds_id))
            menu.addSeparator()
            menu.addAction("在 Finder 中显示", lambda: self._reveal(ds_id))
            menu.addAction("属性...",           lambda: self._show_props(ds_id))
        else:
            menu.addAction("添加数据文件...", self._add_files)
            menu.addAction("添加数据目录...", self._add_folder)
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    # ── 辅助 ────────────────────────────────────────────────────────────────

    def _reveal(self, ds_id: str):
        e = self._dm.get(ds_id)
        if e and os.path.exists(e.path):
            subprocess.Popen(["open", "-R", e.path])

    def _show_props(self, ds_id: str):
        e = self._dm.get(ds_id)
        if not e:
            return
        try:
            sz = os.path.getsize(e.path)
            size_str = (f"{sz/1024/1024:.2f} MB"
                        if sz > 1024 * 1024 else f"{sz/1024:.1f} KB")
        except Exception:
            size_str = "未知"
        QMessageBox.information(
            self, "数据属性",
            f"<b>名称：</b>{e.name}<br>"
            f"<b>类型：</b>{e.dtype}<br>"
            f"<b>大小：</b>{size_str}<br>"
            f"<b>路径：</b><small>{e.path}</small>",
        )

    # ── 外部调用 ────────────────────────────────────────────────────────────

    def reload_from_manager(self):
        """切换工程后刷新整个列表。"""
        self._on_cleared()
        for e in self._dm.all():
            self._on_added(e.ds_id)

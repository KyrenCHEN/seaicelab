"""
数据集管理器
===========
维护当前工程所有已加载数据集，通过 Qt 信号广播变化。
DataPanel 和 AlgoLibrary 都监听这里的信号。
"""

import os
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

# ── 文件扩展名 → 数据类型 ────────────────────────────────────────────────────
_EXT_MAP: dict[str, str] = {
    ".tif":  "GeoTIFF", ".tiff": "GeoTIFF",
    ".nc":   "NetCDF",  ".nc4":  "NetCDF",
    ".h5":   "HDF5",    ".hdf5": "HDF5",
    ".img":  "Binary",  ".dat":  "Binary",
    ".csv":  "CSV",     ".txt":  "文本",
}

# ── 数据类型 → Unicode 图标 ──────────────────────────────────────────────────
DTYPE_ICON: dict[str, str] = {
    "GeoTIFF":  "🗺",
    "NetCDF":   "🌊",
    "HDF5":     "📦",
    "SAR":      "🛰",
    "Optical":  "🌍",
    "Altimeter":"📡",
    "CSV":      "📊",
    "文本":     "📄",
    "Binary":   "💾",
    "Other":    "📁",
}


def guess_dtype(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return _EXT_MAP.get(ext, "Other")


class DataEntry:
    """单个数据集条目（内存中）。"""
    def __init__(self, ds_id: str, name: str, path: str, dtype: str):
        self.ds_id = ds_id
        self.name  = name
        self.path  = path
        self.dtype = dtype

    @property
    def icon(self) -> str:
        return DTYPE_ICON.get(self.dtype, "📁")

    def __repr__(self):
        return f"<DataEntry {self.ds_id} {self.name!r} [{self.dtype}]>"


class DataManager(QObject):
    """
    全局数据集注册表。

    信号：
        dataset_added(ds_id)    — 新数据集注册后
        dataset_removed(ds_id)  — 数据集移除后
        cleared()               — 全部清除后
    """

    dataset_added   = pyqtSignal(str)
    dataset_removed = pyqtSignal(str)
    cleared         = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: dict[str, DataEntry] = {}
        self._counter = 0

    # ── 内部 ────────────────────────────────────────────────────────────────

    def _new_id(self) -> str:
        self._counter += 1
        return f"ds{self._counter:04d}"

    # ── 增删 ────────────────────────────────────────────────────────────────

    def add(self, path: str,
            name:  Optional[str] = None,
            dtype: Optional[str] = None) -> str:
        """注册一个数据文件，返回 ds_id。"""
        ds_id = self._new_id()
        name  = name  or os.path.splitext(os.path.basename(path))[0]
        dtype = dtype or guess_dtype(path)
        self._entries[ds_id] = DataEntry(ds_id, name, path, dtype)
        self.dataset_added.emit(ds_id)
        return ds_id

    def remove(self, ds_id: str):
        if ds_id in self._entries:
            del self._entries[ds_id]
            self.dataset_removed.emit(ds_id)

    def clear(self):
        self._entries.clear()
        self.cleared.emit()

    # ── 查询 ────────────────────────────────────────────────────────────────

    def get(self, ds_id: str) -> Optional[DataEntry]:
        return self._entries.get(ds_id)

    def all(self) -> list[DataEntry]:
        return list(self._entries.values())

    def by_type(self, *dtypes: str) -> list[DataEntry]:
        """按类型过滤；不传 dtypes 则返回全部。"""
        if not dtypes:
            return self.all()
        return [e for e in self._entries.values() if e.dtype in dtypes]

    def __len__(self) -> int:
        return len(self._entries)

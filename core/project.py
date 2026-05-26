"""
工程文件管理
============
.seaice 文件（JSON）记录工程配置：
    name         工程名称
    work_dir     工作目录
    basemap      底图名称
    datasets     已加载数据集列表
    loaded_plugins  已启用插件 ID 列表
"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional

PROJECT_EXT = ".seaice"
_VERSION = "1.0"


@dataclass
class DatasetRecord:
    """工程中存储的一个数据集记录。"""
    name: str
    path: str
    dtype: str = "Other"

    def to_dict(self) -> dict:
        return {"name": self.name, "path": self.path, "dtype": self.dtype}

    @classmethod
    def from_dict(cls, d: dict) -> "DatasetRecord":
        return cls(name=d.get("name", ""), path=d.get("path", ""),
                   dtype=d.get("dtype", "Other"))


@dataclass
class Project:
    name:           str  = "未命名工程"
    work_dir:       str  = ""
    basemap:        str  = "OpenStreetMap"
    datasets:       list = field(default_factory=list)   # list[DatasetRecord]
    loaded_plugins: list = field(default_factory=list)   # list[str]
    file_path: Optional[str] = None   # None = 未保存

    # ── 序列化 ──────────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "version":        _VERSION,
            "name":           self.name,
            "work_dir":       self.work_dir,
            "basemap":        self.basemap,
            "datasets":       [d.to_dict() for d in self.datasets],
            "loaded_plugins": self.loaded_plugins,
        }

    def save(self, path: Optional[str] = None) -> str:
        """保存到 path 或当前 file_path，返回实际保存路径。"""
        target = path or self.file_path
        if not target:
            raise ValueError("未指定保存路径")
        if not target.endswith(PROJECT_EXT):
            target += PROJECT_EXT
        os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        self.file_path = target
        return target

    @classmethod
    def load(cls, path: str) -> "Project":
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return cls(
            name           = d.get("name", "未命名工程"),
            work_dir       = d.get("work_dir", ""),
            basemap        = d.get("basemap", "OpenStreetMap"),
            datasets       = [DatasetRecord.from_dict(x) for x in d.get("datasets", [])],
            loaded_plugins = d.get("loaded_plugins", []),
            file_path      = path,
        )

    @classmethod
    def new(cls, name: str = "未命名工程", work_dir: str = "") -> "Project":
        return cls(name=name, work_dir=work_dir)

    # ── 辅助属性 ────────────────────────────────────────────────────────────

    @property
    def is_saved(self) -> bool:
        return self.file_path is not None

    @property
    def display_name(self) -> str:
        """用于窗口标题，未保存时加 *。"""
        return self.name

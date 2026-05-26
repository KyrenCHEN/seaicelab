from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget
    from core.plugin_manager import PluginContext


class BasePlugin(ABC):
    """
    插件基类。所有插件的 main.py 中必须定义 Plugin(BasePlugin) 子类。

    生命周期：
        on_load(ctx)   -> 插件被加载时调用，ctx 提供平台接口
        on_unload()    -> 插件被卸载时调用，释放资源
        get_panel()    -> 返回插件操作面板 QWidget（显示在左侧停靠区）
        get_viz_tabs() -> 返回附加可视化标签页列表 [(标题, QWidget), ...]
    """

    _meta: dict = {}

    @property
    def name(self) -> str:
        return self._meta.get("name", self.__class__.__name__)

    @property
    def plugin_id(self) -> str:
        return self._meta.get("id", "")

    @property
    def version(self) -> str:
        return self._meta.get("version", "1.0.0")

    @property
    def viz_type(self) -> str:
        return self._meta.get("viz_type", "2d")

    @abstractmethod
    def on_load(self, ctx: "PluginContext"):
        """插件加载。保存 ctx 供后续使用。"""

    @abstractmethod
    def on_unload(self):
        """插件卸载。移除已添加的地图图层和UI元素。"""

    def get_panel(self) -> "QWidget | None":
        """返回左侧面板 Widget，返回 None 表示无面板。"""
        return None

    def get_viz_tabs(self) -> list[tuple[str, "QWidget"]]:
        """返回附加可视化标签页，格式: [(标签名, widget), ...]"""
        return []

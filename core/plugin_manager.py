import importlib.util
import json
import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plugins.base import BasePlugin


class PluginContext:
    """传递给插件的上下文对象，提供平台能力接口"""

    def __init__(self, map_widget, log_fn, event_bus, data_manager=None):
        self.map    = map_widget       # MapWidget 实例
        self.log    = log_fn           # log(msg) 函数
        self.events = event_bus        # EventBus 实例
        self.data   = data_manager     # DataManager 实例（可为 None）


class PluginManager:
    def __init__(self, plugins_dir: str):
        self.plugins_dir = plugins_dir
        self._available: dict[str, dict] = {}   # id -> metadata
        self._loaded: dict[str, "BasePlugin"] = {}  # id -> instance

    def discover(self) -> dict[str, dict]:
        self._available.clear()
        if not os.path.isdir(self.plugins_dir):
            return {}
        for name in sorted(os.listdir(self.plugins_dir)):
            if name.startswith("_") or name.startswith("."):
                continue
            plugin_dir = os.path.join(self.plugins_dir, name)
            meta_file = os.path.join(plugin_dir, "plugin.json")
            main_file = os.path.join(plugin_dir, "main.py")
            if os.path.isdir(plugin_dir) and os.path.exists(meta_file) and os.path.exists(main_file):
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    meta["_dir"] = plugin_dir
                    meta["_folder"] = name
                    self._available[meta["id"]] = meta
                except Exception as e:
                    print(f"[插件管理] 读取 {name}/plugin.json 失败: {e}")
        return self._available

    def load(self, plugin_id: str, context: PluginContext) -> tuple[bool, str]:
        if plugin_id in self._loaded:
            return False, "插件已加载"
        meta = self._available.get(plugin_id)
        if not meta:
            return False, "插件未发现，请先扫描"
        try:
            main_file = os.path.join(meta["_dir"], "main.py")
            module_name = f"_plugin_{plugin_id}"
            spec = importlib.util.spec_from_file_location(module_name, main_file)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            plugin: BasePlugin = module.Plugin()
            plugin._meta = meta
            plugin.on_load(context)
            self._loaded[plugin_id] = plugin
            return True, "加载成功"
        except Exception as e:
            return False, f"加载失败: {e}"

    def unload(self, plugin_id: str) -> tuple[bool, str]:
        if plugin_id not in self._loaded:
            return False, "插件未加载"
        plugin = self._loaded[plugin_id]
        try:
            plugin.on_unload()
        except Exception as e:
            print(f"[插件管理] {plugin_id} 卸载异常: {e}")
        module_name = f"_plugin_{plugin_id}"
        sys.modules.pop(module_name, None)
        del self._loaded[plugin_id]
        return True, "卸载成功"

    def get_loaded(self) -> dict[str, "BasePlugin"]:
        return dict(self._loaded)

    def get_available(self) -> dict[str, dict]:
        return dict(self._available)

    def is_loaded(self, plugin_id: str) -> bool:
        return plugin_id in self._loaded

    def get_plugin(self, plugin_id: str) -> "BasePlugin | None":
        return self._loaded.get(plugin_id)

    def get_loaded_ids(self) -> list[str]:
        return list(self._loaded.keys())

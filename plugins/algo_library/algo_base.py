"""
算法库 — AlgorithmBase 抽象基类
================================
每个反演算法实现此接口，注册到 algo_library 插件后即可通过下拉菜单调用。
不需要单独成为一个插件，共享算法库的 UI 框架、进度条、地图叠加等基础设施。

【新增算法步骤】
1. 在 algorithms/ 目录下新建 my_algo.py
2. 继承 AlgorithmBase，实现 name/description/param_schema/run()
3. 在 algorithms/__init__.py 的 REGISTRY 列表中注册

【参数 schema 格式】
param_schema 返回一个有序列表，每项定义一个 UI 控件：
    {
        "key":     str,   # 参数名（传入 run() 的 params dict）
        "label":   str,   # 界面显示名
        "type":    str,   # "file" | "float" | "int" | "bool" | "choice"
        "default": any,   # 默认值
        # type="file" 额外字段:
        "filter":  str,   # 文件过滤器，如 "GeoTIFF (*.tif *.tiff)"
        # type="float"/"int" 额外字段:
        "min": float, "max": float, "step": float,
        # type="choice" 额外字段:
        "choices": [str, ...],
    }
"""

from abc import ABC, abstractmethod
from typing import Generator


class AlgorithmBase(ABC):
    """
    所有反演算法的抽象基类。
    子类在独立文件中实现，无需继承 BasePlugin，也无需了解 Qt。
    """

    # ── 必须定义的类属性 ─────────────────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """算法显示名称，例如 '基于 ASL 的冰厚反演'"""

    @property
    @abstractmethod
    def description(self) -> str:
        """一段话描述算法原理、适用范围、输入输出"""

    # ── 可选覆盖 ─────────────────────────────────────────────────────────────

    @property
    def param_schema(self) -> list:
        """
        定义算法参数的 UI 控件列表（见模块 docstring）。
        默认只有一个文件选择控件，子类按需覆盖。
        """
        return [
            {
                "key": "input_file", "label": "输入文件",
                "type": "file", "default": "",
                "filter": "GeoTIFF (*.tif *.tiff);;NetCDF (*.nc);;所有文件 (*)"
            },
            {
                "key": "output_file", "label": "输出路径",
                "type": "file_save", "default": "",
                "filter": "GeoTIFF (*.tif *.tiff)"
            },
        ]

    # ── 必须实现的方法 ────────────────────────────────────────────────────────

    @abstractmethod
    def run(self, params: dict) -> Generator:
        """
        算法主体，使用 yield 上报进度（生成器函数）。

        约定：
            yield (int, str)      → 进度百分比 + 状态描述
            yield ("done", dict)  → 算法完成，dict 为结果（见下）
            raise Exception       → 算法失败，框架捕获后显示错误

        结果 dict 可包含：
            "data"   : np.ndarray          # 二维结果，供地图叠加
            "bounds" : (S, W, N, E)        # 地理范围（十进制度）
            "stats"  : {key: value}        # 统计数字，显示在日志
            "output_file" : str            # 已保存的文件路径
            "message"     : str            # 成功提示语

        示例实现：
            def run(self, params):
                yield 10, "读取数据..."
                data = load(params["input_file"])
                yield 50, "反演中..."
                result = invert(data)
                yield 90, "保存..."
                save(result, params["output_file"])
                yield "done", {"data": result, "bounds": (...), "message": "完成"}
        """

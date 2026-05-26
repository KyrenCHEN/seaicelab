"""
示例算法：简单阈值分割
======================
演示 AlgorithmBase 的标准实现。将此文件复制并改造为你的真实算法。
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

import numpy as np
from plugins.algo_library.algo_base import AlgorithmBase


class DemoAlgorithm(AlgorithmBase):

    @property
    def name(self) -> str:
        return "示例：阈值分割"

    @property
    def description(self) -> str:
        return (
            "读取单波段 GeoTIFF，对像元值做阈值分割。\n"
            "大于阈值的像元保留原值，其余设为 NaN。\n"
            "用于演示算法接入流程，可替换为实际反演算法。"
        )

    @property
    def param_schema(self) -> list:
        return [
            {
                "key": "input_file", "label": "输入文件",
                "type": "file", "default": "",
                "filter": "GeoTIFF (*.tif *.tiff);;所有文件 (*)"
            },
            {
                "key": "threshold", "label": "分割阈值",
                "type": "float", "default": 0.5, "min": 0.0, "max": 1e6, "step": 0.1
            },
            {
                "key": "colormap", "label": "色彩映射",
                "type": "choice", "default": "viridis",
                "choices": ["viridis", "plasma", "Blues", "RdYlBu_r", "coolwarm"]
            },
        ]

    def run(self, params: dict):
        """生成器：yield (pct, msg) 上报进度，yield ("done", result) 返回结果。"""
        yield 10, "读取输入文件..."
        try:
            import rasterio
            with rasterio.open(params["input_file"]) as src:
                data = src.read(1).astype(np.float32)
                nodata = src.nodata
                bounds = (
                    src.bounds.bottom, src.bounds.left,
                    src.bounds.top,    src.bounds.right,
                )
        except ImportError:
            data = np.random.rand(256, 256).astype(np.float32)
            bounds = (-90.0, -180.0, 90.0, 180.0)
            nodata = None

        if nodata is not None:
            data[data == nodata] = np.nan

        yield 50, "运行阈值分割..."
        thr = float(params.get("threshold", 0.5))
        result = np.where(data > thr, data, np.nan)

        yield 90, "统计结果..."
        valid = result[~np.isnan(result)]
        stats = {
            "有效像元数": len(valid),
            "均值":       float(valid.mean()) if len(valid) else float("nan"),
            "最大值":     float(valid.max())  if len(valid) else float("nan"),
            "最小值":     float(valid.min())  if len(valid) else float("nan"),
        }

        yield "done", {
            "data":    result,
            "bounds":  bounds,
            "stats":   stats,
            "message": f"分割完成，有效像元 {len(valid)} 个",
        }

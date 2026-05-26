"""
算法注册表
==========
在此列表中添加新算法类即可完成注册，无需修改插件其他代码。

示例：
    from .ice_thickness import IceThicknessAlgorithm
    from .sic_retrieval import SICAlgorithm

    REGISTRY = [
        IceThicknessAlgorithm,
        SICAlgorithm,
    ]
"""

from .demo_algo import DemoAlgorithm

# ★ 在此注册你的算法类 ★
REGISTRY = [
    DemoAlgorithm,
]

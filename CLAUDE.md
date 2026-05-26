# 极地海冰多参数综合反演平台 — 项目说明

## 项目简介

PyQt6 桌面应用，面向极地遥感科研，提供海冰参数反演的数据管理、算法调用与可视化功能。
仿 QGIS 风格界面，插件化架构，支持各子课题算法独立接入。

**运行环境：** conda 环境 `seaice`（Python 3.11）

```bash
conda activate seaice
python main.py
```

---

## 目录结构

```
platform/
├── main.py                  # 入口：显示启动对话框，然后打开主窗口
├── core/                    # 核心业务逻辑（无 UI 依赖）
│   ├── config.py            # 全局配置持久化（JSON）
│   ├── data_manager.py      # 数据集注册表（Qt 信号驱动）
│   ├── events.py            # 简单事件总线（publish/subscribe）
│   ├── license.py           # 硬件 ID + 许可证验证
│   ├── plugin_manager.py    # 插件发现、加载、卸载
│   ├── project.py           # 工程文件（.seaice JSON 格式）
│   └── report.py            # 报告导出
├── ui/                      # 界面组件
│   ├── main_window.py       # 主窗口（QMainWindow，QGIS 风格布局）
│   ├── startup_dialog.py    # 启动欢迎对话框（无边框，780×500）
│   ├── data_panel.py        # 左侧数据管理面板
│   ├── data_selector.py     # 通用数据集选择控件（插件复用）
│   ├── map_widget.py        # 地图控件（Leaflet.js via QWebEngineView）
│   ├── plugin_dialog.py     # 插件管理器对话框
│   ├── report_dialog.py     # 报告导出对话框
│   ├── startup_dialog.py    # 启动对话框
│   └── style.py             # 全局 QSS 样式
└── plugins/                 # 插件目录（每个子目录一个插件）
    ├── base.py              # BasePlugin 抽象基类
    ├── algo_library/        # 算法库插件（动态参数表单）
    ├── demo_2d/             # 冰间水道提取演示（2D 地图叠加）
    ├── demo_3d/             # 三维地物可视化演示（matplotlib 3D）
    ├── demo_track/          # 轨迹演示
    └── _template/           # 新插件模板
```

---

## 核心架构

### 四层架构

```
数据层 (DataManager)
    ↓ pyqtSignal
算法层 (Plugin / AlgorithmBase)
    ↓ 结果
展示层 (MapWidget / matplotlib Canvas)
    ↑
基础设施层 (Project / Config / EventBus)
```

### 插件系统

每个插件是 `plugins/<name>/main.py` 中的 `Plugin(BasePlugin)` 类：

```python
class Plugin(BasePlugin):
    def on_load(self, ctx):   # ctx.map / ctx.log / ctx.events / ctx.data
    def on_unload(self):
    def get_panel(self) -> QWidget:    # 右侧工作区面板
    def get_viz_tabs(self) -> list:    # 中央区额外 Tab
```

`PluginContext` 字段：
- `ctx.map` — MapWidget，提供 `add_geotiff_layer()`, `add_geojson()`, `add_image_overlay()`, `remove_layer()` 等
- `ctx.log(msg)` — 写入底部日志
- `ctx.events` — 事件总线，`publish("status", msg)` / `publish("progress", 0~100)`
- `ctx.data` — DataManager 实例

### DataManager

- `dm.add(path)` → `ds_id`
- `dm.remove(ds_id)`
- `dm.all()` → `[DataEntry]`
- `dm.by_type("GeoTIFF", "NetCDF")` → 过滤
- 信号：`dataset_added(str)`, `dataset_removed(str)`, `cleared()`
- `DataEntry` 属性：`ds_id`, `name`, `path`, `dtype`, `icon`

### 工程文件（.seaice）

JSON 格式，保存：工程名、工作目录、已加载数据集列表、底图、已加载插件 ID 列表。

---

## UI 布局

```
┌─────────────────────────────────────────────────────┐
│  菜单栏 + 工具栏                                      │
├──────────┬──────────────────────────┬───────────────┤
│          │                          │               │
│ 数据面板  │   地图视图 / 可视化 Tab    │  算法工作区   │
│ DataPanel│   MapWidget (Leaflet.js)  │  插件面板 Tab │
│          │                          │               │
├──────────┴──────────────────────────┴───────────────┤
│  日志面板（QPlainTextEdit）                           │
├─────────────────────────────────────────────────────┤
│  状态栏：工程名 · 状态文字 · 进度条                    │
└─────────────────────────────────────────────────────┘
```

---

## 关键设计决策

### DataPanel（左侧数据面板）
- 树形列表，两列（名称 / 类型），均为 Interactive 模式可拖动调整宽度
- **复选框控制地图可见性**：勾选 → `show_on_map` 信号 → MainWindow 调用 `map.add_geotiff_layer()` 或 `map.add_geojson()`；取消勾选 → `hide_from_map` 信号 → `map.remove_layer()`
- 仅 `.tif/.tiff/.geojson/.json` 格式显示复选框；其他格式（NetCDF、HDF5 等）不支持直接可视化
- 双击切换复选框状态；右键菜单根据当前状态显示"在地图中显示"或"从地图中移除"
- 支持拖拽调整顺序（InternalMove）
- 数据移除时自动清理对应地图图层

### DataSelectorWidget（ui/data_selector.py）
通用文件选择控件，所有插件复用：
```python
DataSelectorWidget(
    data_manager=ctx.data,
    dtypes=["GeoTIFF"],           # 可选，过滤类型
    file_filter="GeoTIFF (*.tif)",
    placeholder="选择文件...",
)
sel.get_path()  # 读取当前路径
```
自动订阅 DataManager 信号，数据增删时实时刷新下拉列表。

### MapWidget（Leaflet.js）
- `QWebEngineView` + `QWebChannel` 双向通信
- 主要方法：`add_geotiff_layer()`, `add_geojson()`, `add_image_overlay()`, `remove_layer()`, `clear_all()`, `set_basemap()`
- GeoTIFF 加载：rasterio 读取 → EPSG:4326 重投影 → numpy array → matplotlib colormap → base64 PNG → Leaflet ImageOverlay

### macOS 特殊处理
**无边框窗口（FramelessWindowHint）下，原生对话框必须用 `None` 作 parent，否则崩溃：**
```python
# 正确
name, ok = QInputDialog.getText(None, "标题", "标签:")
# 错误（会崩溃）
name, ok = QInputDialog.getText(self, "标题", "标签:")
```

### 3D 可视化（demo_3d）
matplotlib 3D colorbar 移除顺序：**必须先 `cbar.remove()` 再 `ax.clear()`**，顺序反了会因 subplot spec 变 None 而崩溃。

### 算法接入
在 `plugins/algo_library/algorithms/` 新建 `.py`，继承 `AlgorithmBase`，实现：
- `name`, `description` 属性
- `param_schema` — 参数描述列表，支持类型：`file`, `file_save`, `float`, `int`, `bool`, `choice`, `str`
- `run(params)` — 生成器，`yield (pct, msg)` 上报进度，`yield ("done", result_dict)` 返回结果

`file` 类型参数自动使用 `DataSelectorWidget`，下拉框实时显示已加载数据集。

在 `algorithms/__init__.py` 的 `REGISTRY` 列表中注册即可。

---

## 新增插件步骤

1. 复制 `plugins/_template/` 为 `plugins/<your_plugin>/`
2. 编辑 `main.py`，实现 `Plugin(BasePlugin)`
3. 在 `plugin_manager.py` 发现目录中会自动找到（无需手动注册）
4. 文件输入控件使用 `DataSelectorWidget`，无需手写下拉刷新逻辑

---

## 依赖

```
PyQt6==6.11.0
PyQt6-Qt6==6.11.0
PyQt6-WebEngine==6.11.0
PyQt6-WebEngine-Qt6==6.11.0  (可选，WebEngine 需要)
matplotlib
numpy
rasterio          # GeoTIFF 读取（可选，降级用 PIL）
scipy             # demo_2d 形态学处理（可选）
```

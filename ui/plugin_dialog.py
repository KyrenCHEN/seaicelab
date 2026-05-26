from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)


class PluginManagerDialog(QDialog):
    def __init__(self, plugin_manager, context, parent=None):
        super().__init__(parent)
        self.pm = plugin_manager
        self.ctx = context
        self.setWindowTitle("插件管理器")
        self.resize(700, 460)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        lay.addWidget(splitter)

        # 左：插件列表
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel("可用插件"))
        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.currentItemChanged.connect(lambda cur, _: self._on_select(cur))
        ll.addWidget(self._list)

        btn_row = QHBoxLayout()
        self._btn_load = QPushButton("加载")
        self._btn_load.clicked.connect(self._load)
        self._btn_unload = QPushButton("卸载")
        self._btn_unload.setProperty("secondary", True)
        self._btn_unload.clicked.connect(self._unload)
        self._btn_refresh = QPushButton("重新扫描")
        self._btn_refresh.setProperty("secondary", True)
        self._btn_refresh.clicked.connect(self._refresh)
        btn_row.addWidget(self._btn_load)
        btn_row.addWidget(self._btn_unload)
        btn_row.addWidget(self._btn_refresh)
        ll.addLayout(btn_row)
        splitter.addWidget(left)

        # 右：详情
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 0, 0, 0)
        rl.addWidget(QLabel("插件详情"))
        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        rl.addWidget(self._detail)
        splitter.addWidget(right)

        splitter.setSizes([280, 380])

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.accept)
        lay.addWidget(btns)

    def _refresh(self):
        self.pm.discover()
        self._list.clear()
        for pid, meta in self.pm.get_available().items():
            loaded = self.pm.is_loaded(pid)
            label = f"{'✓ ' if loaded else '  '}{meta.get('name', pid)}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, pid)
            if loaded:
                item.setForeground(Qt.GlobalColor.darkCyan)
            self._list.addItem(item)

    def _current_id(self) -> str | None:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_select(self, item):
        if not item:
            return
        pid = item.data(Qt.ItemDataRole.UserRole)
        meta = self.pm.get_available().get(pid, {})
        loaded = self.pm.is_loaded(pid)
        status = '<span style="color:#00838F">已加载</span>' if loaded else '未加载'
        text = (
            f"<b>名称：</b>{meta.get('name', '')}<br>"
            f"<b>ID：</b>{pid}<br>"
            f"<b>版本：</b>{meta.get('version', '')}<br>"
            f"<b>作者：</b>{meta.get('author', '')}<br>"
            f"<b>可视化类型：</b>{meta.get('viz_type', '')}<br>"
            f"<b>状态：</b>{status}<br><br>"
            f"<b>描述：</b><br>{meta.get('description', '')}"
        )
        self._detail.setHtml(text)
        self._btn_load.setEnabled(not loaded)
        self._btn_unload.setEnabled(loaded)

    def _load(self):
        pid = self._current_id()
        if not pid:
            return
        ok, msg = self.pm.load(pid, self.ctx)
        self._refresh()
        self.ctx.log(f"[插件管理] {msg}")
        if self.parent():
            self.parent()._on_plugin_loaded(pid)

    def _unload(self):
        pid = self._current_id()
        if not pid:
            return
        ok, msg = self.pm.unload(pid)
        self._refresh()
        self.ctx.log(f"[插件管理] {msg}")
        if self.parent():
            self.parent()._on_plugin_unloaded(pid)

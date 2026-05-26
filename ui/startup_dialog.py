"""
启动欢迎对话框
==============
软件启动后弹出，提供：新建工程 / 打开工程 / 最近工程 / 跳过。

返回约定：
    dialog.exec() == QDialog.DialogCode.Accepted → dialog.project 已设置
    dialog.exec() == QDialog.DialogCode.Rejected → 跳过，进入空白界面
"""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.project import Project, PROJECT_EXT
from core import config as cfg


def _add_recent(path: str):
    recents: list = cfg.get("recent_projects", [])
    if path in recents:
        recents.remove(path)
    recents.insert(0, path)
    cfg.set("recent_projects", recents[:12])


class StartupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.project: Project | None = None
        self.setWindowTitle("极地海冰多参数综合反演平台")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(780, 500)
        self._build()

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_left())
        root.addWidget(self._build_divider())
        root.addWidget(self._build_right())

    def _build_left(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(260)
        w.setStyleSheet("background: #0F1E33;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(32, 44, 32, 32)
        lay.setSpacing(14)

        icon = QLabel("🧊")
        icon.setStyleSheet("font-size: 52px; background: transparent;")
        lay.addWidget(icon)

        title = QLabel("极地海冰\n多参数综合\n反演平台")
        title.setStyleSheet(
            "font-size: 19px; font-weight: 700; color: #FFFFFF;"
            "background: transparent; line-height: 1.5;"
        )
        lay.addWidget(title)

        # ver = QLabel("v1.0  ·  SeaIce Lab")
        # ver.setStyleSheet("font-size: 11px; color: #3A5472; background: transparent;")
        # lay.addWidget(ver)

        lay.addStretch()

        skip = QPushButton("跳过，进入空白界面")
        skip.setStyleSheet("""
            QPushButton {
                background: transparent; color: #3A5472;
                border: 1px solid #253547; border-radius: 5px;
                padding: 7px 14px; font-size: 11px;
            }
            QPushButton:hover { color: #7AA0C0; border-color: #3A5472; }
        """)
        skip.clicked.connect(self.reject)
        lay.addWidget(skip)
        return w

    def _build_divider(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setStyleSheet("color: #1E3148;")
        return f

    def _build_right(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(36, 40, 36, 36)
        lay.setSpacing(18)

        # 按钮行
        btn_row = QHBoxLayout()
        new_btn = QPushButton("＋  新建工程")
        new_btn.setFixedHeight(44)
        new_btn.clicked.connect(self._new_project)
        btn_row.addWidget(new_btn)

        open_btn = QPushButton("📂  打开工程...")
        open_btn.setFixedHeight(44)
        open_btn.setProperty("secondary", True)
        open_btn.clicked.connect(self._open_project)
        btn_row.addWidget(open_btn)
        lay.addLayout(btn_row)

        # 最近工程列表
        lbl = QLabel("最近打开的工程")
        lbl.setProperty("subtitle", True)
        lay.addWidget(lbl)

        self._recent = QListWidget()
        self._recent.setAlternatingRowColors(True)
        self._recent.itemDoubleClicked.connect(self._open_recent_item)
        lay.addWidget(self._recent)
        self._load_recents()

        open_sel = QPushButton("打开选中工程")
        open_sel.setProperty("secondary", True)
        open_sel.clicked.connect(
            lambda: self._open_recent_item(self._recent.currentItem())
        )
        lay.addWidget(open_sel)
        return w

    # ── 数据 ────────────────────────────────────────────────────────────────

    def _load_recents(self):
        self._recent.clear()
        recents: list = cfg.get("recent_projects", [])
        found = False
        for path in recents:
            if os.path.exists(path):
                item = QListWidgetItem(
                    f"  {os.path.basename(path)}   —   {os.path.dirname(path)}"
                )
                item.setData(Qt.ItemDataRole.UserRole, path)
                self._recent.addItem(item)
                found = True
        if not found:
            ph = QListWidgetItem("  暂无最近工程")
            ph.setFlags(Qt.ItemFlag.NoItemFlags)
            self._recent.addItem(ph)

    # ── 操作 ────────────────────────────────────────────────────────────────

    def _new_project(self):
        # macOS 无边框窗口下，原生对话框必须用 None 作 parent，否则崩溃
        name, ok = QInputDialog.getText(
            None, "新建工程", "工程名称:", text="未命名工程"
        )
        if not ok or not name.strip():
            return
        work_dir = QFileDialog.getExistingDirectory(None, "选择工作目录")
        if not work_dir:
            return
        self.project = Project.new(name=name.strip(), work_dir=work_dir)
        self.accept()

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            None, "打开工程", "", f"海冰平台工程 (*{PROJECT_EXT});;所有文件 (*)"
        )
        if path:
            self._do_load(path)

    def _open_recent_item(self, item: QListWidgetItem | None):
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self._do_load(path)

    def _do_load(self, path: str):
        try:
            self.project = Project.load(path)
            _add_recent(path)
            self.accept()
        except Exception as e:
            QMessageBox.warning(None, "打开失败", f"无法加载工程文件：\n{e}")

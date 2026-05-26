PALETTE = {
    "nav":          "#0F1E33",
    "nav_light":    "#162B45",
    "accent":       "#00C4E8",
    "accent_dark":  "#009CBB",
    "bg":           "#ECF0F7",
    "surface":      "#FFFFFF",
    "panel":        "#F4F7FC",
    "border":       "#CDD6E8",
    "border_light": "#E4EAF5",
    "text":         "#0D1B2E",
    "text_sec":     "#536578",
    "text_muted":   "#8EA3B8",
    "primary":      "#1565C0",
    "primary_h":    "#1976D2",
    "success":      "#00B88A",
    "warning":      "#F59E0B",
    "error":        "#EF4444",
    "log_bg":       "#080F1A",
    "log_text":     "#55D4F8",
}

_P = PALETTE

STYLESHEET = f"""
/* ── 全局 ─────────────────────────────────── */
QMainWindow, QDialog {{
    background: {_P['bg']};
    font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
    font-size: 13px;
    color: {_P['text']};
}}

/* ── 菜单栏 ───────────────────────────────── */
QMenuBar {{
    background: {_P['nav']};
    color: #C8D8EC;
    padding: 2px 0;
    spacing: 0;
    font-size: 13px;
}}
QMenuBar::item {{
    padding: 7px 16px;
    background: transparent;
}}
QMenuBar::item:selected, QMenuBar::item:pressed {{
    background: rgba(255,255,255,0.10);
    color: #FFFFFF;
}}

/* ── 菜单 ────────────────────────────────── */
QMenu {{
    background: {_P['nav_light']};
    color: #C8D8EC;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px;
    padding: 5px 0;
}}
QMenu::item {{
    padding: 8px 28px 8px 20px;
    border-radius: 0;
}}
QMenu::item:selected {{
    background: {_P['accent']};
    color: {_P['nav']};
    font-weight: 600;
}}
QMenu::item:disabled {{
    color: {_P['text_muted']};
}}
QMenu::separator {{
    height: 1px;
    background: rgba(255,255,255,0.08);
    margin: 4px 12px;
}}
QMenu::indicator:checked {{
    width: 14px;
    height: 14px;
}}

/* ── 工具栏 ───────────────────────────────── */
QToolBar {{
    background: {_P['nav_light']};
    border: none;
    border-bottom: 1px solid rgba(0,0,0,0.25);
    spacing: 2px;
    padding: 4px 10px;
}}
QToolBar::separator {{
    width: 1px;
    background: rgba(255,255,255,0.12);
    margin: 4px 6px;
}}
QToolBar QToolButton {{
    color: #AABFD5;
    background: transparent;
    border: none;
    padding: 5px 12px;
    border-radius: 4px;
    font-size: 12px;
}}
QToolBar QToolButton:hover {{
    background: rgba(255,255,255,0.10);
    color: #FFFFFF;
}}
QToolBar QToolButton:pressed {{
    background: rgba(0,196,232,0.18);
    color: {_P['accent']};
}}
QToolBar QLabel {{
    color: #7A94B0;
    font-size: 12px;
}}
QToolBar QComboBox {{
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.12);
    color: #C8D8EC;
    border-radius: 4px;
    padding: 3px 6px;
    font-size: 12px;
}}
QToolBar QComboBox::drop-down {{ border: none; width: 18px; }}
QToolBar QComboBox QAbstractItemView {{
    background: {_P['nav_light']};
    color: #C8D8EC;
    border: 1px solid rgba(255,255,255,0.12);
    selection-background-color: {_P['accent']};
    selection-color: {_P['nav']};
}}

/* ── Dock 标题栏 ─────────────────────────── */
QDockWidget::title {{
    background: {_P['panel']};
    color: {_P['text_sec']};
    padding: 7px 12px;
    font-weight: 600;
    font-size: 12px;
    letter-spacing: 0.3px;
    border-bottom: 1px solid {_P['border']};
}}
QDockWidget::close-button, QDockWidget::float-button {{
    border: none;
    background: transparent;
    padding: 2px;
}}
QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
    background: rgba(0,0,0,0.08);
    border-radius: 3px;
}}

/* ── Tab 控件 ────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {_P['border']};
    border-radius: 0;
    background: {_P['surface']};
}}
QTabWidget::tab-bar {{
    alignment: left;
}}
QTabBar {{
    font-size: 12px;
}}
QTabBar::tab {{
    background: {_P['panel']};
    color: {_P['text_sec']};
    padding: 7px 18px;
    border: 1px solid {_P['border']};
    border-bottom: none;
    min-width: 72px;
}}
QTabBar::tab:first {{
    border-left: 1px solid {_P['border']};
}}
QTabBar::tab:selected {{
    background: {_P['surface']};
    color: {_P['primary']};
    font-weight: 700;
    border-top: 2px solid {_P['accent']};
    border-bottom: none;
}}
QTabBar::tab:hover:!selected {{
    background: {_P['border_light']};
    color: {_P['text']};
}}
QTabBar::close-button {{
    padding: 1px;
    border-radius: 3px;
}}
QTabBar::close-button:hover {{
    background: rgba(239,68,68,0.15);
}}

/* 底部 Tab（地图区）—— 选中指示线在底部 */
QTabWidget#center_tabs QTabBar::tab {{
    border: 1px solid {_P['border']};
    border-top: none;
    border-bottom: none;
    padding: 6px 16px;
}}
QTabWidget#center_tabs QTabBar::tab:selected {{
    background: {_P['surface']};
    color: {_P['primary']};
    font-weight: 700;
    border-top: none;
    border-bottom: 2px solid {_P['accent']};
}}

/* ── 按钮 ────────────────────────────────── */
QPushButton {{
    background: {_P['primary']};
    color: #FFFFFF;
    border: none;
    padding: 7px 20px;
    border-radius: 5px;
    font-size: 13px;
    font-weight: 600;
    min-width: 72px;
}}
QPushButton:hover {{
    background: {_P['primary_h']};
}}
QPushButton:pressed {{
    background: #0D47A1;
}}
QPushButton:disabled {{
    background: {_P['border']};
    color: {_P['text_muted']};
}}
QPushButton[secondary=true] {{
    background: {_P['panel']};
    color: {_P['text_sec']};
    border: 1px solid {_P['border']};
}}
QPushButton[secondary=true]:hover {{
    background: {_P['border_light']};
    color: {_P['text']};
    border-color: {_P['text_muted']};
}}

/* ── 输入控件 ────────────────────────────── */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {_P['surface']};
    border: 1px solid {_P['border']};
    border-radius: 4px;
    padding: 5px 9px;
    color: {_P['text']};
    selection-background-color: {_P['accent']};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1.5px solid {_P['accent']};
}}
QLineEdit:read-only {{
    background: {_P['panel']};
    color: {_P['text_sec']};
}}

QComboBox {{
    background: {_P['surface']};
    border: 1px solid {_P['border']};
    border-radius: 4px;
    padding: 5px 9px;
    color: {_P['text']};
}}
QComboBox:focus {{
    border: 1.5px solid {_P['accent']};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {_P['surface']};
    border: 1px solid {_P['border']};
    selection-background-color: {_P['accent']};
    selection-color: {_P['nav']};
    outline: none;
}}

/* ── 文本区 ──────────────────────────────── */
QTextEdit, QPlainTextEdit {{
    background: {_P['surface']};
    border: 1px solid {_P['border']};
    border-radius: 4px;
    color: {_P['text']};
    font-size: 12px;
}}

/* 日志专用：暗色终端风格 */
QPlainTextEdit#log_edit {{
    background: {_P['log_bg']};
    color: {_P['log_text']};
    border: none;
    border-radius: 0;
    font-family: "Consolas", "Courier New", "Menlo", monospace;
    font-size: 11px;
    padding: 6px 10px;
    selection-background-color: #1A4060;
}}

/* ── 列表 / 树 / 表格 ───────────────────── */
QListWidget, QTreeWidget, QTableWidget {{
    background: {_P['surface']};
    border: 1px solid {_P['border']};
    border-radius: 4px;
    outline: none;
    alternate-background-color: {_P['panel']};
    gridline-color: {_P['border_light']};
}}
QListWidget::item, QTreeWidget::item, QTableWidget::item {{
    padding: 5px 8px;
    border-bottom: 1px solid {_P['border_light']};
}}
QListWidget::item:selected, QTreeWidget::item:selected,
QTableWidget::item:selected {{
    background: #DFF0FF;
    color: {_P['primary']};
}}
QListWidget::item:hover:!selected,
QTreeWidget::item:hover:!selected {{
    background: {_P['panel']};
}}
QHeaderView::section {{
    background: {_P['panel']};
    color: {_P['text_sec']};
    padding: 6px 10px;
    border: none;
    border-right: 1px solid {_P['border']};
    border-bottom: 1px solid {_P['border']};
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.3px;
}}

/* ── 进度条 ───────────────────────────────── */
QProgressBar {{
    background: {_P['border']};
    border: none;
    border-radius: 4px;
    height: 7px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {_P['accent']}, stop:1 {_P['primary']});
    border-radius: 4px;
}}

/* ── 滑块 ────────────────────────────────── */
QSlider::groove:horizontal {{
    height: 4px;
    background: {_P['border']};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {_P['accent']};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
    border: 2px solid {_P['surface']};
}}
QSlider::sub-page:horizontal {{
    background: {_P['accent']};
    border-radius: 2px;
}}

/* ── 状态栏 ──────────────────────────────── */
QStatusBar {{
    background: {_P['nav']};
    color: {_P['text_muted']};
    font-size: 11px;
    padding: 2px 10px;
    border-top: 1px solid rgba(255,255,255,0.05);
}}
QStatusBar QLabel {{ color: {_P['text_muted']}; }}
QStatusBar QProgressBar {{
    background: rgba(255,255,255,0.08);
    border-radius: 3px;
    height: 5px;
}}
QStatusBar QProgressBar::chunk {{
    background: {_P['accent']};
    border-radius: 3px;
}}

/* ── 滚动条 ──────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {_P['border']};
    min-height: 30px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: {_P['text_muted']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
}}
QScrollBar::handle:horizontal {{
    background: {_P['border']};
    min-width: 30px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {_P['text_muted']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── 分组框 ──────────────────────────────── */
QGroupBox {{
    border: 1px solid {_P['border']};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 12px;
    font-weight: 700;
    font-size: 12px;
    color: {_P['text_sec']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 12px;
    color: {_P['text_sec']};
}}

/* ── 分割器 ──────────────────────────────── */
QSplitter::handle:horizontal {{
    width: 2px;
    background: {_P['border']};
}}
QSplitter::handle:vertical {{
    height: 2px;
    background: {_P['border']};
}}

/* ── 标签语义样式 ─────────────────────────── */
QLabel[title=true] {{
    font-size: 15px;
    font-weight: 700;
    color: {_P['text']};
    padding-bottom: 2px;
}}
QLabel[subtitle=true] {{
    font-size: 12px;
    color: {_P['text_sec']};
}}

/* ── 对话框按钮区 ────────────────────────── */
QDialogButtonBox QPushButton {{
    min-width: 80px;
}}
"""

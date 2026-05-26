import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401（必须在 QApplication 前导入）

from core.license import LicenseManager
from ui.style import STYLESHEET


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("极地海冰多参数综合反演平台")
    app.setOrganizationName("SeaIce Lab")
    app.setStyleSheet(STYLESHEET)

    # ── 授权检查 ─────────────────────────────────────────────────────────────
    lm = LicenseManager()
    ok, msg = lm.check()
    if not ok:
        from ui.license_dialog import LicenseDialog
        dlg = LicenseDialog(lm)
        dlg.setStyleSheet(STYLESHEET)
        if dlg.exec() != 1:
            sys.exit(0)

    # ── 启动欢迎对话框 ───────────────────────────────────────────────────────
    from ui.startup_dialog import StartupDialog
    startup = StartupDialog()
    startup.setStyleSheet(STYLESHEET)

    project = None
    if startup.exec() == StartupDialog.DialogCode.Accepted:
        project = startup.project   # 新建或已加载的 Project

    # ── 主窗口 ───────────────────────────────────────────────────────────────
    from ui.main_window import MainWindow
    win = MainWindow(project=project, license_info=lm.get_info())
    win.resize(1440, 880)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

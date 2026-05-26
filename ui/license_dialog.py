from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget,
)


class LicenseDialog(QDialog):
    def __init__(self, license_manager, parent=None):
        super().__init__(parent)
        self.lm = license_manager
        self.setWindowTitle("软件授权")
        self.setFixedSize(480, 380)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)

        header = QLabel("极地海冰多参数综合反演平台")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setProperty("title", True)
        lay.addWidget(header)

        sub = QLabel("请输入授权信息以继续使用")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setProperty("subtitle", True)
        lay.addWidget(sub)
        lay.addSpacing(8)

        tabs = QTabWidget()
        lay.addWidget(tabs)

        # Tab1: 管理员代码
        admin_tab = QWidget()
        atl = QVBoxLayout(admin_tab)
        atl.setContentsMargins(16, 16, 16, 16)
        atl.setSpacing(12)
        atl.addWidget(QLabel("输入管理员授权代码："))
        self._admin_edit = QLineEdit()
        self._admin_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._admin_edit.setPlaceholderText("SEAICE-ADMIN-XXXX")
        atl.addWidget(self._admin_edit)
        btn_admin = QPushButton("使用管理员代码激活")
        btn_admin.clicked.connect(self._activate_admin)
        atl.addWidget(btn_admin)
        self._admin_status = QLabel("")
        self._admin_status.setProperty("subtitle", True)
        atl.addWidget(self._admin_status)
        atl.addStretch()
        tabs.addTab(admin_tab, "管理员激活")

        # Tab2: 许可证文件
        lic_tab = QWidget()
        ltl = QVBoxLayout(lic_tab)
        ltl.setContentsMargins(16, 16, 16, 16)
        ltl.setSpacing(12)
        ltl.addWidget(QLabel("粘贴许可证密钥："))
        self._lic_edit = QTextEdit()
        self._lic_edit.setPlaceholderText("将许可证Base64字符串粘贴至此处...")
        self._lic_edit.setFixedHeight(80)
        ltl.addWidget(self._lic_edit)
        btn_lic = QPushButton("激活许可证")
        btn_lic.clicked.connect(self._activate_license)
        ltl.addWidget(btn_lic)
        self._lic_status = QLabel("")
        self._lic_status.setProperty("subtitle", True)
        ltl.addWidget(self._lic_status)
        ltl.addStretch()
        tabs.addTab(lic_tab, "许可证激活")

        # Tab3: 硬件信息
        hw_tab = QWidget()
        hwl = QVBoxLayout(hw_tab)
        hwl.setContentsMargins(16, 16, 16, 16)
        hwl.setSpacing(8)
        hwl.addWidget(QLabel("将以下硬件ID提供给管理员以获取许可证："))
        hw_id_edit = QLineEdit(self.lm.get_hardware_id())
        hw_id_edit.setReadOnly(True)
        hw_id_edit.setStyleSheet("font-family: monospace; font-size: 12px;")
        hwl.addWidget(hw_id_edit)
        btn_copy = QPushButton("复制硬件ID")
        btn_copy.clicked.connect(lambda: self._copy(hw_id_edit.text()))
        hwl.addWidget(btn_copy)
        hwl.addStretch()
        tabs.addTab(hw_tab, "硬件信息")

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        btn_box.rejected.connect(self.reject)
        lay.addWidget(btn_box)

    def _activate_admin(self):
        code = self._admin_edit.text().strip()
        ok, msg = self.lm.activate_admin(code)
        if ok:
            self._admin_status.setStyleSheet("color: #43A047;")
            self._admin_status.setText(f"✓ {msg}")
            self.accept()
        else:
            self._admin_status.setStyleSheet("color: #E53935;")
            self._admin_status.setText(f"✗ {msg}")

    def _activate_license(self):
        text = self._lic_edit.toPlainText().strip()
        ok, msg = self.lm.activate_license(text)
        if ok:
            self._lic_status.setStyleSheet("color: #43A047;")
            self._lic_status.setText(f"✓ {msg}")
            self.accept()
        else:
            self._lic_status.setStyleSheet("color: #E53935;")
            self._lic_status.setText(f"✗ {msg}")

    def _copy(self, text: str):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)

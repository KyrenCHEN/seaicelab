"""
导出报告对话框
支持 HTML / PDF / DOCX 三种格式，包含地图截图、插件图表、元数据等内容。
"""

import os
from datetime import datetime

from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)


class _ExportWorker(QThread):
    progress     = pyqtSignal(str)
    result_ready = pyqtSignal(list)   # 不用 finished 避免与 QThread.finished 冲突
    failed       = pyqtSignal(str)

    def __init__(self, config, assets, parent=None):
        super().__init__(parent)
        self._config = config
        self._assets = assets

    def run(self):
        import sys, os
        # 确保 core 可 import
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if root not in sys.path:
            sys.path.insert(0, root)

        from core.report import export_html, export_pdf, export_docx

        cfg     = self._config
        assets  = self._assets
        out_dir = cfg.out_dir or os.path.expanduser("~")
        ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
        base    = os.path.join(out_dir, f"seaice_report_{ts}")
        exported = []

        try:
            if cfg.fmt_html:
                path = base + ".html"
                self.progress.emit("正在生成 HTML...")
                export_html(cfg, assets, path)
                exported.append(path)

            if cfg.fmt_pdf:
                path = base + ".pdf"
                self.progress.emit("正在生成 PDF...")
                export_pdf(cfg, assets, path)
                exported.append(path)

            if cfg.fmt_docx:
                path = base + ".docx"
                self.progress.emit("正在生成 Word 文档...")
                export_docx(cfg, assets, path)
                exported.append(path)

            self.result_ready.emit(exported)
        except Exception as e:
            import traceback
            self.failed.emit(traceback.format_exc())


class ReportDialog(QDialog):
    """导出报告配置对话框。"""

    def __init__(self, map_widget, plugin_manager, parent=None):
        super().__init__(parent)
        self._map = map_widget
        self._pm  = plugin_manager
        self._worker = None

        self.setWindowTitle("导出分析报告")
        self.setMinimumWidth(460)
        self.setModal(True)
        self._build_ui()
        self._check_deps()

    # ── UI 构建 ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(18, 18, 18, 18)

        # 报告基本信息
        grp_info = QGroupBox("报告信息")
        f = QFormLayout(grp_info)
        self._title_edit = QLineEdit("海冰多参数综合反演分析报告")
        self._author_edit = QLineEdit()
        self._author_edit.setPlaceholderText("可选")
        self._note_edit = QLineEdit()
        self._note_edit.setPlaceholderText("可选")
        f.addRow("标题:", self._title_edit)
        f.addRow("作者:", self._author_edit)
        f.addRow("备注:", self._note_edit)
        lay.addWidget(grp_info)

        # 报告内容
        grp_content = QGroupBox("报告内容")
        cl = QVBoxLayout(grp_content)
        self._chk_map  = QCheckBox("地图视图截图")
        self._chk_map.setChecked(True)
        self._chk_figs = QCheckBox("分析结果图（已渲染的插件图表）")
        self._chk_figs.setChecked(True)
        self._chk_meta = QCheckBox("元数据信息（时间、作者等）")
        self._chk_meta.setChecked(True)
        cl.addWidget(self._chk_map)
        cl.addWidget(self._chk_figs)
        cl.addWidget(self._chk_meta)
        lay.addWidget(grp_content)

        # 输出格式
        grp_fmt = QGroupBox("输出格式")
        fl = QVBoxLayout(grp_fmt)
        self._chk_html = QCheckBox("HTML（内嵌图片，可直接浏览器打开）")
        self._chk_html.setChecked(True)
        self._chk_pdf  = QCheckBox("PDF（需安装 reportlab）")
        self._chk_docx = QCheckBox("Word .docx（需安装 python-docx）")
        fl.addWidget(self._chk_html)
        fl.addWidget(self._chk_pdf)
        fl.addWidget(self._chk_docx)
        self._dep_label = QLabel("")
        self._dep_label.setWordWrap(True)
        self._dep_label.setStyleSheet("color: #888; font-size: 11px;")
        fl.addWidget(self._dep_label)
        lay.addWidget(grp_fmt)

        # 输出目录
        grp_out = QGroupBox("保存位置")
        ol = QHBoxLayout(grp_out)
        self._out_edit = QLineEdit(os.path.expanduser("~/Desktop"))
        btn_browse = QPushButton("浏览...")
        btn_browse.setFixedWidth(70)
        btn_browse.setProperty("secondary", True)
        btn_browse.clicked.connect(self._browse_dir)
        ol.addWidget(self._out_edit)
        ol.addWidget(btn_browse)
        lay.addWidget(grp_out)

        # 进度 & 状态
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)   # 无限模式
        self._progress.setVisible(False)
        lay.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setStyleSheet("color: #5580a0; font-size: 11px;")
        lay.addWidget(self._status)

        # 按钮行
        btn_row = QHBoxLayout()
        self._export_btn = QPushButton("生成报告")
        self._export_btn.clicked.connect(self._run)
        cancel_btn = QPushButton("取消")
        cancel_btn.setProperty("secondary", True)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._export_btn)
        lay.addLayout(btn_row)

    def _check_deps(self):
        """检查可选依赖并更新 UI 提示。"""
        try:
            from core.report import check_deps
        except ImportError:
            return
        deps = check_deps()
        msgs = []
        if not deps["pdf"]:
            self._chk_pdf.setEnabled(False)
            self._chk_pdf.setText("PDF（未安装 reportlab，已禁用）")
            msgs.append("pip install reportlab  # 启用 PDF")
        if not deps["docx"]:
            self._chk_docx.setEnabled(False)
            self._chk_docx.setText("Word .docx（未安装 python-docx，已禁用）")
            msgs.append("pip install python-docx  # 启用 Word")
        if msgs:
            self._dep_label.setText("安装缺失库以启用更多格式：\n" + "\n".join(msgs))

    # ── 交互 ────────────────────────────────────────────────────────────────

    def _activate_map_tab(self):
        """找到包含地图 Widget 的 QTabWidget 并切换到地图 Tab，确保 WebEngine 可见。"""
        from PyQt6.QtWidgets import QApplication, QTabWidget
        from PyQt6.QtCore import QEventLoop, QTimer

        # 向上遍历父窗口的所有 QTabWidget，找到包含 self._map 的那个
        main_win = self.parent()
        if main_win is None:
            return
        for tw in main_win.findChildren(QTabWidget):
            for i in range(tw.count()):
                if tw.widget(i) is self._map:
                    tw.setCurrentIndex(i)
                    # 刷新事件队列，确保 Tab 切换已生效
                    QApplication.processEvents()
                    return

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择保存目录",
                                             self._out_edit.text())
        if d:
            self._out_edit.setText(d)

    def _run(self):
        if not (self._chk_html.isChecked() or
                self._chk_pdf.isChecked() or
                self._chk_docx.isChecked()):
            QMessageBox.warning(self, "提示", "请至少选择一种输出格式。")
            return

        import sys
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if root not in sys.path:
            sys.path.insert(0, root)

        from core.report import (
            ReportConfig, ReportAssets,
            collect_map_screenshot, collect_viz_figures,
        )

        # 构建配置
        cfg = ReportConfig(
            title           = self._title_edit.text().strip() or "分析报告",
            author          = self._author_edit.text().strip(),
            note            = self._note_edit.text().strip(),
            include_map     = self._chk_map.isChecked(),
            include_figures = self._chk_figs.isChecked(),
            include_meta    = self._chk_meta.isChecked(),
            fmt_html        = self._chk_html.isChecked(),
            fmt_pdf         = self._chk_pdf.isChecked() and self._chk_pdf.isEnabled(),
            fmt_docx        = self._chk_docx.isChecked() and self._chk_docx.isEnabled(),
            out_dir         = self._out_edit.text().strip(),
        )

        # 收集地图截图：
        #   1. 切换到地图 Tab
        #   2. 把对话框设为全透明（不能 hide，否则 macOS modal session 会崩）
        #   3. 等待系统重绘后截图
        #   4. 恢复透明度
        map_png = None
        if cfg.include_map:
            self._activate_map_tab()
            self._status.setText("正在截取地图...")
            self.setWindowOpacity(0.0)
            map_png = collect_map_screenshot(self._map)
            self.setWindowOpacity(1.0)

        self._status.setText("正在抓取插件图表...")
        figures = collect_viz_figures(self._pm) if cfg.include_figures else []

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metadata = {}
        loaded = self._pm.get_loaded_ids()
        if loaded:
            metadata["已加载插件"] = "、".join(
                (self._pm.get_plugin(p).name if self._pm.get_plugin(p) else p)
                for p in loaded
            )
        metadata["图表数量"] = str(len(figures))

        assets = ReportAssets(
            timestamp = ts,
            map_png   = map_png,
            figures   = figures,
            metadata  = metadata,
        )

        # 启动后台导出线程
        self._export_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status.setText("正在生成文件...")

        self._worker = _ExportWorker(cfg, assets, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.result_ready.connect(self._on_done)
        self._worker.failed.connect(self._on_fail)
        # QThread.finished（无参）：线程 run() 结束后自动 emit，用于安全销毁
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_progress(self, msg: str):
        self._status.setText(msg)

    def _on_done(self, paths: list):
        self._progress.setVisible(False)
        self._export_btn.setEnabled(True)

        if not paths:
            self._status.setText("未生成任何文件。")
            return

        names = "\n".join(os.path.basename(p) for p in paths)
        out_dir = os.path.dirname(paths[0])
        self._status.setText(f"生成完成：{names}")

        msg = QMessageBox(self)
        msg.setWindowTitle("导出成功")
        msg.setText(f"报告已生成：\n{chr(10).join(paths)}")
        msg.setIcon(QMessageBox.Icon.Information)
        open_btn = msg.addButton("打开所在目录", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton("关闭", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        if msg.clickedButton() is open_btn:
            import subprocess, platform
            if platform.system() == "Darwin":
                subprocess.Popen(["open", out_dir])
            elif platform.system() == "Windows":
                os.startfile(out_dir)
            else:
                subprocess.Popen(["xdg-open", out_dir])

    def _on_fail(self, tb: str):
        self._progress.setVisible(False)
        self._export_btn.setEnabled(True)
        self._status.setText("生成失败，请查看详情。")
        QMessageBox.critical(self, "导出失败", tb[:1200])

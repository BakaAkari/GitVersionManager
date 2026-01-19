"""
Git Version Manager - Main Window

Uses Services layer for all business logic operations.
"""
import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QLabel, QFrame,
    QSplitter, QMessageBox, QFileDialog, QMenu, QAction, QProgressBar,
    QTextEdit, QGroupBox, QComboBox, QDialog, QFormLayout, QStyle
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QFont, QDragEnterEvent, QDropEvent

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Services layer - primary interface for business logic
from services import ProjectService, VersionService, PublishService
from core.config_manager import ConfigManager

# GUI components
from gui.icon_utils import IconUtils
from gui.workers import (
    WorkerThread, RefreshWorker, BuildWorker, PackageWorker, 
    PublishWorker, ProjectStatusWorker, SyncStatusWorker, SyncOperationWorker
)
from gui.widgets import ProjectItem
from gui.dialogs import SettingsDialog, SyncDialog, ProjectDialog, AddProjectDialog


class MainWindow(QMainWindow):
    """Main application window."""
    
    AUTO_REFRESH_INTERVALS = {
        "不自动检查": 0,
        "5分钟": 5 * 60 * 1000,
        "15分钟": 15 * 60 * 1000,
        "30分钟": 30 * 60 * 1000
    }
    
    def __init__(self):
        super().__init__()
        # Initialize config and services
        self.config = ConfigManager()
        self.project_service = ProjectService(self.config)
        self.version_service = VersionService()
        self.publish_service = PublishService(self.config)
        
        self.current_project = None
        self.current_item = None
        self.worker = None
        
        # Auto-refresh timer
        self.auto_refresh_timer = QTimer(self)
        self.auto_refresh_timer.timeout.connect(self.on_auto_refresh)
        
        self.setWindowTitle("Git Version Manager")
        self.setMinimumSize(900, 600)
        
        # Set window icon (works in both dev and bundled mode)
        if getattr(sys, 'frozen', False):
            # Running as bundled exe
            base_path = sys._MEIPASS
        else:
            # Running as script
            base_path = os.path.dirname(os.path.dirname(__file__))
        icon_path = os.path.join(base_path, "resources", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setAcceptDrops(True)
        
        
        self.setup_ui()
        self.load_projects()
    
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        
        # Left panel - Project list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.project_list = QListWidget()
        self.project_list.setMinimumWidth(200)
        self.project_list.itemClicked.connect(self.on_project_selected)
        self.project_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.project_list.customContextMenuRequested.connect(self.show_project_context_menu)
        left_layout.addWidget(self.project_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("+ 添加")
        add_btn.clicked.connect(self.add_project)
        settings_btn = QPushButton("")
        settings_btn.setIcon(IconUtils.create_menu_icon())
        settings_btn.setFixedWidth(40)
        settings_btn.clicked.connect(self.open_settings)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(settings_btn)
        left_layout.addLayout(btn_layout)
        
        # Right panel - Project details
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Project info
        info_group = QGroupBox("项目信息")
        info_layout = QFormLayout(info_group)
        
        self.name_label = QLabel("-")
        self.name_label.setFont(QFont("", 12, QFont.Bold))
        info_layout.addRow("名称:", self.name_label)
        
        self.path_label = QLabel("-")
        info_layout.addRow("路径:", self.path_label)
        
        self.type_label = QLabel("-")
        info_layout.addRow("类型:", self.type_label)
        
        self.local_version_label = QLabel("-")
        self.local_version_label.setStyleSheet("color: #b0b0b0;")
        info_layout.addRow("本地版本:", self.local_version_label)
        
        # Per-platform remote versions
        self.remote_versions_widget = QWidget()
        remote_versions_layout = QVBoxLayout(self.remote_versions_widget)
        remote_versions_layout.setContentsMargins(0, 0, 0, 0)
        remote_versions_layout.setSpacing(2)
        
        self.github_version_label = QLabel("▶ GitHub: -")
        self.github_version_label.setStyleSheet("color: #b0b0b0;")
        remote_versions_layout.addWidget(self.github_version_label)
        
        self.gitee_version_label = QLabel("▶ Gitee: -")
        self.gitee_version_label.setStyleSheet("color: #b0b0b0;")
        remote_versions_layout.addWidget(self.gitee_version_label)
        
        self.gitea_version_label = QLabel("▶ Gitea: -")
        self.gitea_version_label.setStyleSheet("color: #b0b0b0;")
        remote_versions_layout.addWidget(self.gitea_version_label)
        
        info_layout.addRow("远程版本:", self.remote_versions_widget)
        
        self.status_label = QLabel("-")
        info_layout.addRow("状态:", self.status_label)
        
        right_layout.addWidget(info_group)
        
        # Actions - only 4 core functions
        actions_group = QGroupBox("操作")
        actions_layout = QHBoxLayout(actions_group)
        
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.refresh_btn.clicked.connect(self.refresh_project)
        actions_layout.addWidget(self.refresh_btn)
        

        
        self.sync_btn = QPushButton("同步管理")
        self.sync_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.sync_btn.clicked.connect(self.open_sync_dialog)
        actions_layout.addWidget(self.sync_btn)
        
        # Auto-refresh dropdown
        actions_layout.addWidget(QLabel("自动刷新:"))
        self.auto_refresh_combo = QComboBox()
        self.auto_refresh_combo.addItems(list(self.AUTO_REFRESH_INTERVALS.keys()))
        self.auto_refresh_combo.currentTextChanged.connect(self.on_auto_refresh_changed)
        actions_layout.addWidget(self.auto_refresh_combo)
        
        right_layout.addWidget(actions_group)
        
        # Log (stretches with window)
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(80)
        log_layout.addWidget(self.log_text)
        
        right_layout.addWidget(log_group, 1)  # stretch factor 1
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        right_layout.addWidget(self.progress_bar)
        
        right_layout.addStretch()
        
        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([250, 650])
        
        main_layout.addWidget(splitter)
    
    def log(self, message: str):
        """Add message to log."""
        self.log_text.append(message)
    
    def load_projects(self):
        """Load projects from config via ProjectService."""
        self.project_list.clear()
        self.status_workers = []  # Track workers for parallel check
        
        projects = self.project_service.get_all_projects()
        for project in projects:
            item = ProjectItem(project)
            item.set_status("checking")  # Show checking status
            self.project_list.addItem(item)
        
        # Start parallel status check for all projects
        if projects:
            self.log(f"🔍 正在检查 {len(projects)} 个项目状态...")
            self.check_all_projects_parallel()
    
    def check_all_projects_parallel(self):
        """Check status of all projects in parallel."""
        for i in range(self.project_list.count()):
            item = self.project_list.item(i)
            if isinstance(item, ProjectItem):
                worker = ProjectStatusWorker(item.project_data)
                worker.finished.connect(self.on_project_status_checked)
                self.status_workers.append(worker)
                worker.start()
    
    def on_project_status_checked(self, path: str, status: str, local_version: str):
        """Handle status check result for a single project."""
        # Find the matching project item
        for i in range(self.project_list.count()):
            item = self.project_list.item(i)
            if isinstance(item, ProjectItem):
                if item.project_data.get("path") == path:
                    item.set_status(status, local_version)
                    break
        
        # Check if all done
        all_done = all(
            not w.isRunning() for w in getattr(self, 'status_workers', [])
        )
        if all_done and hasattr(self, 'status_workers') and self.status_workers:
            self.log("✅ 所有项目状态检查完成")
            self.status_workers = []
    
    def on_auto_refresh_changed(self, text: str):
        """Handle auto-refresh interval change."""
        interval = self.AUTO_REFRESH_INTERVALS.get(text, 0)
        
        if interval > 0:
            self.auto_refresh_timer.start(interval)
            self.log(f"⏱️ 自动刷新已启用: {text}")
        else:
            self.auto_refresh_timer.stop()
            self.log("⏱️ 自动刷新已关闭")
    
    def on_auto_refresh(self):
        """Handle auto-refresh timer timeout."""
        self.log("⏱️ 自动刷新中...")
        for i in range(self.project_list.count()):
            item = self.project_list.item(i)
            if isinstance(item, ProjectItem):
                item.set_status("checking")
        self.check_all_projects_parallel()
    
    def add_project(self):
        """Add a new project via ProjectService."""
        dialog = AddProjectDialog(self)
        if dialog.exec_() == QDialog.Accepted and dialog.project_data:
            if self.project_service.add_project(dialog.project_data):
                self.load_projects()
                self.log(f"添加项目: {dialog.project_data['path']}")
            else:
                QMessageBox.warning(self, "错误", "项目已存在")
    

    def on_project_selected(self, item: ProjectItem):
        """Handle project selection - display cached status."""
        self.current_project = item.project_data
        self.current_item = item
        self.update_project_display()
        
        # Display cached status from ProjectItem
        if item.local_version:
            self.local_version_label.setText(item.local_version)
        else:
            self.local_version_label.setText("-")
        
        # Display cached platform status
        cached = item.cached_status
        platform_status = cached.get("platform_status", {})
        
        if "github" in platform_status:
            status, color = platform_status["github"]
            self.github_version_label.setText(f"▶ GitHub: {status}")
            self.github_version_label.setStyleSheet(f"color: {color};")
        else:
            self.github_version_label.setText("▶ GitHub: -")
            self.github_version_label.setStyleSheet("color: gray;")
        
        if "gitee" in platform_status:
            status, color = platform_status["gitee"]
            self.gitee_version_label.setText(f"▶ Gitee: {status}")
            self.gitee_version_label.setStyleSheet(f"color: {color};")
        else:
            self.gitee_version_label.setText("▶ Gitee: -")
            self.gitee_version_label.setStyleSheet("color: gray;")
        
        if "gitea" in platform_status:
            status, color = platform_status["gitea"]
            self.gitea_version_label.setText(f"▶ Gitea: {status}")
            self.gitea_version_label.setStyleSheet(f"color: {color};")
        else:
            self.gitea_version_label.setText("▶ Gitea: -")
            self.gitea_version_label.setStyleSheet("color: gray;")
        
        # Display cached git status
        has_changes = cached.get("has_changes", False)
        ahead = cached.get("ahead", 0)
        behind = cached.get("behind", 0)
        last_check = cached.get("last_check")
        
        if last_check:
            status_parts = []
            if has_changes:
                status_parts.append("⚠️ 有未提交修改")
            if ahead > 0:
                status_parts.append(f"⬆️ 领先 {ahead} 个提交")
            if behind > 0:
                status_parts.append(f"⬇️ 落后 {behind} 个提交")
            if not status_parts:
                status_parts.append("✅ 已同步")
            self.status_label.setText(" | ".join(status_parts))
        else:
            self.status_label.setText("点击刷新按钮检查详细状态")
    
    def update_project_display(self):
        """Update the project info display."""
        if not self.current_project:
            return
        
        path = self.current_project.get("path", "")
        self.name_label.setText(os.path.basename(path))
        self.path_label.setText(path)
        self.type_label.setText(self.current_project.get("type", "unknown"))
    
    def refresh_project(self):
        """Refresh project status asynchronously."""
        if not self.current_project:
            return
        
        if hasattr(self, 'refresh_worker') and self.refresh_worker and self.refresh_worker.isRunning():
            self.log("⏳ 刷新正在进行中...")
            return
        
        path = self.current_project.get("path", "")
        project_type = self.current_project.get("type", "")
        
        self.log(f"🔄 刷新项目: {os.path.basename(path)}")
        self.status_label.setText("🔄 正在刷新...")
        self.refresh_btn.setEnabled(False)
        
        # Create and start worker
        self.refresh_worker = RefreshWorker(path, project_type)
        self.refresh_worker.progress.connect(self.log)
        self.refresh_worker.update_label.connect(self.on_refresh_update_label)
        self.refresh_worker.finished.connect(self.on_refresh_finished)
        self.refresh_worker.start()
    
    def on_refresh_update_label(self, label_name: str, text: str, color: str):
        """Handle label updates from worker thread."""
        if label_name == "local_version":
            self.local_version_label.setText(text)
            self.local_version_label.setStyleSheet(f"color: {color};")
    
    def on_refresh_finished(self, result: dict):
        """Handle refresh completion."""
        self.refresh_btn.setEnabled(True)
        
        platform_status = result.get("platform_status", {})
        has_changes = result.get("has_changes", False)
        ahead = result.get("ahead", 0)
        behind = result.get("behind", 0)
        
        # Update platform labels
        for platform, label in [
            ("github", self.github_version_label),
            ("gitee", self.gitee_version_label),
            ("gitea", self.gitea_version_label)
        ]:
            if platform in platform_status:
                status, color = platform_status[platform]
                label.setText(f"▶ {platform.capitalize()}: {status}")
                label.setStyleSheet(f"color: {color};")
            else:
                label.setText(f"▶ {platform.capitalize()}: 未配置")
                label.setStyleSheet("color: gray;")
        
        # Overall status
        status_parts = []
        if has_changes:
            status_parts.append("⚠️ 有未提交修改")
        if ahead > 0:
            status_parts.append(f"⬆️ 领先 {ahead} 个提交")
        if behind > 0:
            status_parts.append(f"⬇️ 落后 {behind} 个提交")
        if not status_parts:
            status_parts.append("✅ 已同步")
        
        self.status_label.setText(" | ".join(status_parts))
        
        # Update list item status and cache
        current_item = self.project_list.currentItem()
        if isinstance(current_item, ProjectItem):
            local_version = result.get("local_version")
            if local_version:
                local_version_str = self.version_service.version_to_string(local_version)
                current_item.local_version = local_version_str
            
            current_item.set_status(result.get("item_status", "unknown"))
            current_item.set_cached_status(
                platform_status, has_changes, ahead, behind, result.get("changed_files")
            )
        
        

    def build_project(self):
        """Build the project (execute build script for python_app)."""
        if not self.current_project:
            return
        
        if hasattr(self, 'build_worker') and self.build_worker and self.build_worker.isRunning():
            self.log("⏳ 编译正在进行中...")
            return
        
        path = self.current_project.get("path", "")
        project_type = self.current_project.get("type", "")
        
        if project_type != "python_app":
            self.log("❌ 只有 python_app 类型需要编译")
            return
        
        default_dir = path
        if os.path.exists(os.path.join(path, "build.bat")):
            default_dir = os.path.join(path, "build.bat")
        
        build_script, _ = QFileDialog.getOpenFileName(
            self, "选择构建脚本 (.bat)", default_dir, "Batch Files (*.bat);;All Files (*)"
        )
        
        if not build_script:
            self.log("⚠️ 已取消编译 (未选择构建脚本)")
            return
        
        self.log(f"🔨 开始编译项目...")
        
        self.build_worker = BuildWorker(build_script)
        self.build_worker.progress.connect(self.log)
        self.build_worker.finished.connect(self.on_build_finished)
        self.build_worker.start()
    
    def on_build_finished(self, success: bool, result: str):
        """Handle build completion."""
        if success:
            self.log("✅ 编译成功，可以执行打包了")
        else:
            self.log(f"❌ 编译失败: {result}")
    
    def package_project(self):
        """Package the project as ZIP using PublishService."""
        if not self.current_project:
            return
        
        if hasattr(self, 'package_worker') and self.package_worker and self.package_worker.isRunning():
            self.log("⏳ 打包正在进行中...")
            return
        
        path = self.current_project.get("path", "")
        project_name = os.path.basename(path)
        project_type = self.current_project.get("type", "")
        
        # Use VersionService to get version
        version = self.version_service.get_version_string(path, project_type)
        archive_path = self.config.get_archive_path() or os.path.dirname(path)
        
        self.log(f"📦 开始打包 {project_name}...")
        
        self.package_worker = PackageWorker(path, project_name, archive_path, version, project_type)
        self.package_worker.progress.connect(self.log)
        self.package_worker.finished.connect(self.on_package_finished)
        self.package_worker.start()
    
    def on_package_finished(self, success: bool, result: str):
        """Handle package completion."""
        if success:
            self.last_zip_path = result
    
    def publish_project(self):
        """Publish project to configured platforms using PublishService."""
        if not self.current_project:
            return
        
        if hasattr(self, 'publish_worker') and self.publish_worker and self.publish_worker.isRunning():
            self.log("⏳ 发布正在进行中...")
            return
        
        path = self.current_project.get("path", "")
        project_name = os.path.basename(path)
        project_type = self.current_project.get("type", "")
        publish_to = self.current_project.get("publish_to", [])
        
        if not publish_to:
            QMessageBox.warning(self, "警告", "未配置发布平台")
            return
        
        # Use services to get version and check zip
        version = self.version_service.get_version_string(path, project_type)
        zip_path = self.publish_service.get_zip_path(self.current_project)
        
        if not zip_path:
            archive_path = self.config.get_archive_path() or os.path.dirname(path)
            zip_filename = f"{project_name}_v{version}.zip"
            reply = QMessageBox.question(
                self, "确认",
                f"未找到打包文件: {zip_filename}\n是否先进行打包？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.package_project()
                self.log("⚠️ 打包完成后请再次点击发布")
                return
            else:
                return
        
        self.log(f"🚀 开始发布 {project_name} v{version}...")
        
        self.publish_worker = PublishWorker(
            path, project_name, version, zip_path,
            publish_to, self.current_project, self.config
        )
        self.publish_worker.progress.connect(self.log)
        self.publish_worker.finished.connect(self.on_publish_finished)
        self.publish_worker.start()
    
    def on_publish_finished(self, results: dict):
        """Handle publish completion."""
        self.refresh_project()
    
    def open_sync_dialog(self):
        """Open the git sync management dialog."""
        if not self.current_project:
            QMessageBox.warning(self, "提示", "请先选择一个项目")
            return
        
        path = self.current_project.get("path", "")
        dialog = SyncDialog(path, self)
        dialog.exec_()
        self.refresh_project()
    
    def show_project_context_menu(self, pos):
        """Show context menu for project list."""
        item = self.project_list.itemAt(pos)
        if not item:
            return
        
        menu = QMenu(self)
        
        edit_action = QAction("✏️ 编辑设置", self)
        edit_action.triggered.connect(lambda: self.edit_project(item))
        menu.addAction(edit_action)
        
        sync_action = QAction("🔄 同步管理", self)
        sync_action.triggered.connect(lambda: self.open_sync_for_item(item))
        menu.addAction(sync_action)
        
        open_action = QAction("📁 打开目录", self)
        open_action.triggered.connect(lambda: self.project_service.open_in_explorer(item.project_data.get("path", "")))
        menu.addAction(open_action)
        
        menu.addSeparator()
        
        remove_action = QAction("🗑️ 移除", self)
        remove_action.triggered.connect(lambda: self.remove_project(item))
        menu.addAction(remove_action)
        
        menu.exec_(self.project_list.mapToGlobal(pos))
    
    def open_sync_for_item(self, item: ProjectItem):
        """Open sync dialog for a specific project item."""
        path = item.project_data.get("path", "")
        dialog = SyncDialog(path, self)
        dialog.exec_()
    
    def edit_project(self, item: ProjectItem):
        """Edit a project's settings via ProjectService."""
        dialog = ProjectDialog(self, project_data=item.project_data)
        if dialog.exec_() == QDialog.Accepted and dialog.project_data:
            path = item.project_data.get("path", "")
            self.project_service.update_project(path, dialog.project_data)
            self.load_projects()
            self.log(f"项目设置已更新: {os.path.basename(path)}")
    
    def remove_project(self, item: ProjectItem):
        """Remove a project from the list via ProjectService."""
        reply = QMessageBox.question(
            self, "确认",
            f"确定要移除项目 {os.path.basename(item.project_data.get('path', ''))} 吗？\n（不会删除实际文件）",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.project_service.remove_project(item.project_data.get("path", ""))
            self.load_projects()
            self.log("项目已移除")
    
    def open_settings(self):
        """Open settings dialog."""
        dialog = SettingsDialog(self.config, self)
        dialog.exec_()
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        """Handle drop - add dropped folders as projects via ProjectService."""
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                project_type = self.project_service.detect_project_type(path) or "custom"
                project_data = {
                    "path": path,
                    "type": project_type,
                    "publish_to": [],
                    "github_repo": "",
                    "gitee_repo": "",
                    "gitea_repo": ""
                }
                if self.project_service.add_project(project_data):
                    self.load_projects()
                    self.log(f"添加项目: {path}")


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Apply dark theme
    from gui.styles import apply_dark_theme
    apply_dark_theme(app)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
